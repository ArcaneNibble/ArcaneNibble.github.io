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
