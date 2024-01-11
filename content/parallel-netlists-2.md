Title: Parallel-capable netlist data structures, part 2
Date: 2024-01-01
Summary: TODO TODO TODO
Status: draft

# Issues with the current code

The throwaway code from last time has a few immediately-obvious issues:

## The `connect_*`/`disconnect_*` abstractions aren't being used

These functions were pretty clearly suboptimal for the logic that was needed (disconnecting some existing connections and, at the same time, replacing them with connections to a newly-added cell).

This is a "simple matter of API design" that can be improved with new functions (such as explicit "swap" operations). As such, this can be deferred until "later."

## Manually acquiring read/write guards and retrying operations

There are currently no abstractions to help with making sure the correct locks are acquired, causing the following issues:

1. Every single `try_read()` and `try_write()` manually handles errors

    Every single lock operation has to be manually followed by a check for an error, potentially re-queuing the current cell and continuing, and an `unwrap()`. Messing this up will cause a hard-to-debug logic error (which happened at least once while I was writing the code).

2. You need to commit to read vs. write ahead of time

    If a read lock has already been acquired, there isn't any way to "upgrade" it to a write lock. It is also not possible to subsequently acquire a separate write lock (even on the same thread) because there are already readers.

3. There isn't any obvious way to extend this for algorithms that require ordering

    In order to support "ordered" algorithms, we need some way to perform speculative execution but buffer the actual write/modify operations until the operation commits. (In the worst case, this might result in unavoidable serialization.) There isn't an obvious way to implement this, as the only boundary identifying the "actual writes" is currently a `// actual updates` line.

# Properly encapsulating graph operations

Through discussing this API surface with a friend, we have collectively come up with the following design:

* Operations are split into an explicit "read-only" phase and a "read-write" phase.

    This commits us to the restriction of "all algorithms that the netlist API helps you with must be 'cautious' as defined in the Pingali et al. paper."

    Because many (and likely most of the ones we will need) operations on netlists can be rewritten into this form, I will consider this a perfectly acceptable trade-off in exchange for being able to speculatively execute operations concurrently.

    With this split, it also becomes possible to defer the "read-write" phase to a later time when implementing an "ordered" algorithm. The following is one way to do that:

    * The data passed from the RO phase to the RW phase is explicitly stored into a `struct` which must be `Send`

    * When the RO phase finishes, the RW phase isn't (necessarily) run immediately. Instead, this resulting `struct` is stored in some kind of commit pool.

    * When the write is finally ready to commit, the RW phase is finally called (which can be from a different thread).

    * If the write is instead aborted, the RW phase is never run.

    * If an operation is instead unordered, the RW phase can be run immediately after the RO phase on the same thread, as an optimization.

    There is a potential concern with this split: if the graph manipulating operator is "expensive" in some way, how should this cost be split? Should most of the work be performed in the read-only phase or the read-write phase? How much does this matter in practice? For now, I have chosen to ignore this problem.

* The read-only phase (somehow) tells the framework which nodes will be written in the read-write phase. All locks acquired in the read-only phase will have one of the following states in the read-write phase: still read-only, upgraded to read-write, or released.

    The framework will then automatically handle "upgrading" the required locks.

    For an "unordered" algorithm, failure to upgrade a lock results in the current operation being abandoned and retried later.

    For an "ordered" algorithm, something more complicated has to happen. The Kulkarni et al. paper explains one way to do this using _iteration locks_. (Note that that paper describes the commit pool as containing an undo log, rather than our implementation of storing a write callback and simply not doing the work until commit time.) This seems to make sense but requires a bunch more engineering effort, so I will simply hope that everything will work out in the end 🙃.

# Okay, let's build it!

If we are going to separate out read-only and read-write phases, it would probably involve separating the phases into separate functions. In order to hold on to locks across them, we need a `struct` of some kind:

```rust
#[derive(Debug)]
pub struct CellLockWip<'a> {
    idx: usize,
    r: Option<RwLockReadGuard<'a, NetlistCell>>,
    w: Option<RwLockWriteGuard<'a, NetlistCell>>,
}
```

And a corresponding function for acquiring a lock:

```rust
impl NetlistModule {
    // ... other functions omitted

    pub fn lock_cell_for_read_ro_phase(&self, idx: usize) -> Option<CellLockWip> {
        let cell = self.cells.get(idx).unwrap();
        Some(CellLockWip {
            idx,
            r: Some(cell.try_read().ok()?),
            w: None,
        })
    }
}
```

Hmm, it doesn't work though...

```text
error[E0515]: cannot return value referencing local variable `cell`
   --> sicl4_db/src/test_slab_nonblock.rs:167:9
    |
167 | /         Some(CellLockWip {
168 | |             idx,
169 | |             r: Some(cell.try_read().ok()?),
    | |                     ---- `cell` is borrowed here
170 | |             w: None,
171 | |         })
    | |__________^ returns a value referencing data owned by the current function
```

It turns out that no amount of trying to hack around this can make this work. The description of `sharded_slab::Entry` actually explains why, but I failed to realize the implications.

In a `sharded_slab`, it is possible for another thread to attempt to free an item that the current thread is still working on. A `sharded_slab::Entry` prevents this from causing problems by deferring the free until all guards are dropped. In my code, I had been making an implicit assumption that freeing an entry is only possible with a write guard held (i.e. the current thread is the only one that can possibly see the node to be freed). However, the `sharded_slab` crate knows nothing about the locking I am doing.

It seems like trying to hang on to *both* the `Entry` *and* `RwLock*Guard` objects should work in theory, but the limitations of the Rust borrow checker prevent this (the `RwLock` guard lifetime needs to be at least as long as the `Entry` lifetime, but this would result in a self-referential struct).

The Kulkarni et al. paper also happens to mention that freeing entries should only happen when a write operation commits. I had not considered that I would need to actually enforce this 

It looks like I need to actually start implementing all of the data structures I need "for real" instead of trying to quickly duct-tape together existing pieces that only approximately do what I want.

However, at this point, it would appear that I have a decent idea what exactly I would even need to implement:

* Netlist nodes are stored in an arena, ["essentially a way to group up allocations that are expected to have the same lifetime"](https://manishearth.github.io/blog/2021/03/15/arenas-in-rust/)
* There needs to be some kind of integration with per-node reader-writer locks
    * This is needed for the aforementioned object freeing issue
    * The framework needs to know about locks in order to deal with algorithms requiring order
    * Allowing the netlist framework to have visibility into locks potentially allows for more advanced work scheduling in the future
* A work-stealing task queue (possibly by reusing an existing one, but it needs to know what to do with speculatively executing ordered algorithms)
* Probably a slab allocator, for memory locality and to avoid hitting the system allocator extremely hard
* Actually build out proper APIs mentioned at the very beginning of this article
* Actually build out a proper "wire" and "port <-> wire" system like Yosys's

# Okay, _now_ let's build it!

