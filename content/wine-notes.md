Title: Notes on Wine architecture and process startup
Date: 2025-02-23
Summary: A little braindump about Wine

I've had a number of project ideas floating around for a long time which would all at some point involve emulating limited parts of Windows. I wanted to know how easy it would be to reuse only some of the [Wine](https://www.winehq.org/) source code. None of the ideas involve just running a Windows program directly like a normal user (otherwise I'd just use Wine as is).

In order to even be able to mentally scope out and estimate the complexity of some of these ideas, I wanted to know "various low-level details of how Wine works." The Wine [Architecture Overview](https://gitlab.winehq.org/wine/wine/-/wikis/Wine-Developer%27s-Guide/Architecture-Overview) doesn't go into the level of detail I wanted to know, and this question is rather poorly-scoped and open-ended, so I finally decided to get my hands dirty and figure it out for myself. Since I had to do that, I figured I would share my thought process and what I have found.

This is also an attempt to convince myself to do more technical writing that isn't a "fully complete" deep dive into something, and to hopefully convince and remind myself that not every piece of writing has to be absolutely perfect.

# Wine process startup

One place to start investigating low-level details is to start from the very beginning. We start by installing Wine (both the `wine64` and `wine32` packages) and mingw-w64 on a Ubuntu 24.04 test virtual machine. We can compile a "hello world" program using mingw-w64 and run the result in Wine. Once that works, we can start digging.

## Debian-related complexity

On Ubuntu, `/usr/bin/wine` is a symlink to `/etc/alternatives/wine` (the Debian "alternatives" system) which in turn points to `/usr/bin/wine-stable`.

This in turn is a Debian-packaging-specific shell script which will suggest the necessary commands for installing the `wine32` package if it cannot find it. This finally invokes `/usr/lib/wine/wine` or `/usr/lib/wine/wine64`.

At this point, I download the Ubuntu package source (using `apt-get source`) to reference alongside the (more-easily searched but a newer version) [mirror of Wine's code on GitHub](https://github.com/wine-mirror/wine). After changing into the resulting `wine-9.0~repack` directory, running `gdb` on Wine's binaries loads up the correct source code.

## Initial loader

When poking around Wine's source code, the [`loader/`](https://github.com/wine-mirror/wine/tree/master/loader) directory immediately stands out. Inside `loader/main.c`, there is eventually a call to `__wine_main` inside ntdll. However, `tools/wine/wine.c` *also* calls this function, and the `loader/` directory also contains a "preloader" which does even more complicated stuff. Which one of these is actually used?

This is the point where using `gdb` is helpful. Even though the code isn't a perfect match, we can set breakpoints on `_start`, `main`, and `wld_main` (from the preloader). When we run the program, it ends up hitting the entry point of the normal glibc dynamic loader (`ld.so`) followed by `main` in `loader/main.c`. This seems to indicate that the `/usr/lib/wine/wine` and `/usr/lib/wine/wine64` binaries are compiled from `loader/`, the preloader is not used, and `tools/wine/wine.c` does something else entirely.

Because I also wanted to understand how Wine implemented WOW64 and why the Linux gaming/tech press (especially Phoronix) was so excited about the "PE conversion" project, I intentionally created a 32-bit test executable and loaded it with the `wine64` binary.

Other than mangling some path-related stuff, this loader quickly calls into `dlls/ntdll/unix/loader.c`.

## ntdll, ELF version

The initial loader loads ntdll using the `dlopen` function which can only open ELF libraries. This ends up loading `/usr/lib/x86_64-linux-gnu/wine/x86_64-unix/ntdll.so`. At this point, the environment is still an entirely normal Linux user process.

The `/usr/lib/x86_64-linux-gnu/wine/x86_64-unix/` contains only very few ELF `.so` files, and they all seem to relate to libraries where Wine needs to interact with the host system.

One of the first things that `__wine_main` does is to check for the `WINELOADERNOEXEC` environment variable. If it is not set, some annoying stuff is done in order to do something which is somehow related to architecture switching and reinvoking the preloader. However, since the preloader isn't being used and the entire point was to investigate "low-level" details, I didn't care about this.

In order to simplify tracing in gdb and not have to deal with following the process as it calls `exec`, I set the `WINELOADERNOEXEC` environment variable in the current shell. When the program is rerun, it goes through the "real" process startup.

During the "real" startup, the calls to `virtual_init` and `init_environment` perform yet more setup which I was not very interested in. However, `init_environment` did map locale-related data into memory (which can be seen in gdb using `info proc map`). Code finally flows into the `start_main_thread` function.

## No WOW64 for you

The `start_main_thread` function starts setting up data structures that would be found in a Windows process such as the Process Environment Block (PEB) and the Thread Environment Block (TEB). It also launches and connects to the `wineserver` process.

When tracing through line-by-line, `init_startup_info` seems to perform a lot of work. At the end of it, we can see that `/usr/lib/x86_64-linux-gnu/wine/x86_64-windows/start.exe` has been mapped into memory. Uh, what is `start.exe`? It turns out that this is used to "start a program using ShellExecuteEx, optionally wait for it to finish."

It turns out that this version of Wine which is part of Ubuntu doesn't seem to actually support the WOW64 mode I was thinking of and which was being hyped up (where a 32-bit Windows process can be run while only requiring 64-bit Linux libraries).

## Entering the PE world.

After accepting defeat and switching to the 32-bit Wine loader, it is possible to trace through the same code paths again. This time, our test executable is actually mapped into memory. Other stuff is set up, and the *PE* version of ntdll is mapped into memory. `server_init_process_done` is called, even more stuff happens, and finally `signal_start_thread` is called which performs the magic to switch into a "Windows-like" environment. In the 32-bit version, it calls `call_init_thunk` which sets up a context in order to return to `LdrInitializeThunk` inside the PE version of ntdll. At this point I no longer know how to set up gdb to load appropriate symbols to continue debugging.

Code past this point seems to be written "mostly as if it were Windows."

# How does Wine magic work?

## OpenMPT

[OpenMPT](https://openmpt.org) is a music tracker for Windows that officially supports running under Wine. As part of that, in order to get better audio performance (reduction of pops and glitches), it can bypass all of the emulation layers and call native Linux sound APIs such as PulseAudio directly. How does it do that?

[Poking around its source code](https://github.com/OpenMPT/openmpt/blob/master/build/wine/wine_wrapper.mk), it uses `winegcc` to build a `.dll.so` file. Wine's PE loader (inside `dlls/ntdll/loader.c`) will attempt to process files which don't start with a MZ header as possibly being a native library. This file contains a function `load_so_dll` which calls back into the Linux environment and handles dealing with this. This is done by using the `WINE_UNIX_CALL` macro which eventually (after much fiddling) makes a call through the `__wine_unixlib_handle` variable in order to reach the `load_so_dll` inside `dlls/ntdll/unix/loader.c` (note the `unix` directory). This eventually calls `dlopen`, meaning that the `.dll.so` can directly link native Linux libraries. The rest is tied together using "build system magic."

I don't know if a `.dll.so` can call Windows APIs in addition to Linux APIs. If it can, I also don't know how this gets implemented.

## Wine built-in libraries

Libraries for functions handling e.g. GUIs also need to interact between the emulated Windows environment and the Linux environment. Many of these also go through the same `WINE_UNIX_CALL` macro. However, the build system magic used for Wine's built-in libraries seems to be slightly different. I hate build systems, so I haven't poked how this works.

## WOW64?

It is pretty clear that WOW64 (if it were to be enabled) works by having the libraries which need to deal with the Windows<->Linux boundary contain two sets of functions. For example, many DLLs contain both a `__wine_unix_call_funcs` array and also a `__wine_unix_call_wow64_funcs` array. One set deals with same-bitness calls while the other does whatever is needed to handle 32-bit-to-64-bit calls.

The actual steps involved in getting the CPU to run 32-bit code seem to be entirely as expected. Everything which is accessible to 32-bit code needs to be in the lower 4 GiB of the address space, and the CS segment register is changed to tell the CPU to perform the actual switch. This is the same architecture as WOW64 on Windows, and the infosec space had (very many years ago) given this the silly name "Heaven's Gate."

It is not clear why there is a connection between "converting to PE" and implementing WOW64 in this way, unless this was merely an opportunity to refactor the code into its current form.

# Conclusion

I figured out what I wanted to understand. That's... about it.

