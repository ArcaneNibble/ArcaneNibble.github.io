Title: Parallel-capable netlist data structures, part 3
Date: 2024-01-01
Summary: In which I learn about out-of-order execution...
status: draft

Now that the fundamental primitives are written, we can start hack hack hacking on implementing netlist internals, right?

Not so fast, let's make sure that algorithms requiring order can be implemented, rather than "I will simply hope that everything will work out in the end 🙃" from the last post.

# Algorithms requiring order

The papers ([1](https://iss.oden.utexas.edu/Publications/Papers/pingali11.pdf) [2](https://sci-hub.wf/10.1145/1250734.1250759)) inspiring all of this are using _agglomerative clustering_ as an example algorithm requiring order. This may or may not be the most useful thing for a netlist/EDA package (perhaps logic simulation might be more useful), but let's stick with it for now and think about how it might be implemented.

First of all, we need some way of replacing two netlist cells with a "cluster" cell, which needs to have references to the two sub-cells. Storing the reference isn't a problem, but we do need to figure out a data model that will allow extension attributes on cells. I'm leaving such "data model" issues as a "later" problem.

As mentioned last time, the plan was to divide algorithms into a read-only "prepare" phase where all of the necessary locks are acquired (but no data is modified yet) and a read-write "commit" phase (where the data modification actually happens). While thinking about this while staring at the hacky benchmark, one thing stood out: we are currently adding new work to the task queue in the "commit" phase. This obviously does work, but is this what the Kulkarni et al. paper is actually doing? It turns out, **no**!

The Kulkarni et al. paper mentions using a poset (which our framework will be providing as part of the executor) and a kd-tree (which would need to be external), and it spends a bunch of time talking about semantic commutativity on *both* of these data structures. Hmm... our brain is getting hints of potential problems...

## Speculative execution

The "oh DUH" realization finally struck when staring at the Figure 9 commutativity rules for a `Set`, specifically that there are commutativity rules around `get()` -- the model described in the paper allows _speculative execution_! Not just a limited amount of speculating stuff already existing in the work queue, but _an entire forest_ of speculative computations. In fact, for agglomerative clustering, the paper mentions that "However, on occasion, we must speculate over 100 elements deep into the ordered set to continue making forward progress."

However, speculative execution has a downside in that, in pathological cases, it can end up performing huge amounts of wasted work. We probably want some way to control whether or not speculation is allowed, or at least how much is allowed.

It turns out that allowing new work to be added to the task queue in the read-only phase in our model corresponds to allowing more than one level of speculative execution. Deferring those additions to the read-write phase corresponds to allowing much more limited speculation only within the work queues.

Allowing for unlimited speculative execution now causes interesting problems. In order to be able to perform speculative execution for agglomerative clustering, we need to be able to modify the kd-tree (in order to continue speculating past a single level). But this can potentially invalidate in-flight computations being performed elsewhere which end up using data that we've speculatively modified (even if that other operation isn't being speculated and will definitely happen). **This** is why the paper is describing their (seemingly hand-checked) commutativity rules and undo logs.

Which means that our framework needs to provide some type of "undo" and "verify that we can still commit" callbacks. The question becomes how much of that we need _now_ vs in the future, as not every algorithm needs this (e.g. anything that only makes modifications inside the netlist itself and not any external data structures doesn't need this).

For now, we just need to keep in mind that whatever we implement has to make it possible to find and invalidate all of the computations that have been performed downstream of a canceled speculative execution.

## Cancelling operations

How exactly *do* we detect that a speculative execution needs to be canceled? There's all of the stuff about commutativity violations which we will set aside for now, but what about only within the netlist? Obviously, _something_ has to get canceled if `try_read()` or `try_write()` fail. But what?

In order for locking to fail, a _write_ has to be involved somewhere. Let's try to enumerate all of the cases that can happen between two _pending_ operations:

* (read-)write followed by (read-)write
    * and the first RW has higher priority -- the second operation has to be canceled
    * and the second RW has higher priority -- the first operation has to be canceled
* (read-)write followed by read-only
    * and the first RW has higher priority -- the second operation has to be canceled, because the first operation hasn't actually _committed_ yet, so we don't have its data available
    * and the second RO has higher priority -- hmm, we _should_ be able to continue nonetheless as long as we know that the first RW operation commits _after_ the second RO operation
* read-only followed by (read-)write
    * and the first RO has higher priority -- hmmm, we _should_ once again be able to continue both operations? the RO operation cannot overwrite data that we speculatively read now
    * and the second RW has higher priority -- the first operation has to be canceled as the write invalidates the data that the first operation used

Whoops, it turns out that simple, straightforward reader-writer locks aren't the correct model for this! (although they're fine for the unordered-commits-immediately algorithms like the hacky benchmark has been doing)

I guess it's time to look into how modern CPUs manage out-of-order execution... (it might be a better or at least different mental model to have vs commutativity)

## Stretching the hardware analogy

Let's see how far we can push the analogy between speculative netlist modification and CPU speculative execution. Firstly, the work queue is analogous to a CPU instruction stream. Unlike an instruction stream, the work queue is a priority queue, and adding new items can cause the desired instruction sequence to get reshuffled. Notably, a low-priority work item can queue something with higher priority (in a single-threaded executor, this will then be executed immediately).

Netlist nodes are analogous to registers. Unlike CPU registers, the number of nodes we can have is unbounded, and their size is also unbounded (i.e. we do not want to be duplicating nodes).

The number of threads we have running our algorithm is analogous to CPU functional units.

The problem we need to be detecting would be referred to as a _hazard_ in CPU design. One major difference is that in a CPU instruction set there are relatively few registers, so potential hazards occur all the time. In a large graph data structure, there are effectively a ton of registers, so hazards are relatively unlikely. Even if a hazard does occur, if there is a lot of pending work then it would be quite likely that it might be possible to find some other non-conflicting work to do instead of stalling.

Unlike when designing a CPU, our algorithms here aren't limited by a fixed number of physical wires between different parts of the algorithm. However, physical wires are vaguely analogous to global state, locks, and contention which do affect our performance.

The Kulkarni et al. paper is already describing their _commit pool_ data structure as similar to a CPU's reorder buffer.

And finally, the "hmm we _should_ be able to continue?" cases observed above are solved in CPUs using _register renaming_. We should ~handwaves~ somehow be able to do something similar by tracking the priority of attempted writes to each object? But this is probably about as far as the analogy can go. Time to flip back to the software viewpoint.

## Back to software

So... how *do* we implement said hand-waving? Preferably without adding lists inside netlist nodes which can end up growing unboundedly in size?

The obvious approach is to just _have_ said lists and make every netlist node store a list of outstanding writes to it. Trying to acquire a lock on the node will check for hazards.

The other obvious approach is to make the commit pool store a record of every write it is going to make, and then having all of the locking functions scan through the entire commit pool to check for hazards.

Now that we're in a software mindset again, we can try using a nice software trick for moving queues out of the lock object -- hashing the address! This trick is used for futexes, parking lot locks, etc.

Let's suppose we had some kind of concurrent hashtable mapping `(node_address) -> ???`. What do we need to put in it? Let's suppose we store a list of pending writes and their priorities. What will our locking functions do?

If we are trying to acquire a read-only lock, this is allowed as long as we have higher priority than anything in the list.

If we are trying to acquire a read-write lock... oops, there can only be _one_ pending read-write lock per node! Because the second one might depend on data written by the first one.

Whelp, it turns out that the "commit" (vs "undo") model inherently limits us to one level of speculation. You can't mix-and-match both models (Imagine e.g. performing agglomerative clustering and trying to manipulate the kd-tree with undo, but the netlist itself defers writes. The kd-tree would end up referencing nodes that don't even exist yet!) Which also implies that we might as well restrict "add new tasks to queue" to the commit phase.

There is still parallelism extractable with this model! Just not as much!

Okay, fine, let's see where this gets us before we have to go figure out how to make all netlist operations undo-able. The only change we now have to make to locking is "a read-only lock of higher priority can still read from a write-locked node, as long as it hasn't committed yet."

Incidentally, we need some way for write operations that detect conflicts to cancel the other operation, so we need some way to go from netlist node -> other iteration's commit pool entry. There might be at most one _write_ to cancel, but there can be an unbounded number of _reads_ to cancel.

Oops, so we need to store all outstanding reads as well as writes. Oh! But, with the "commit" model, the pending commit data structure _already_ has to store all of those. We just need a way to link multiple of them together.

So one possible implementation we could potentially use is: "single global task queue (with locks), single global commit queue (with locks), single global hashtable (with locks), iteration records (with individual lock), 'prepare' phase `try_write` is the normal one, `try_read` can ~somehow~ atomically barge past a lower-priority pending write."
