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
