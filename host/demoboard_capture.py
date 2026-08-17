"""Run a sweep using ONLY the Tiny Tapeout demo board — no extra hardware.

Path B of two (see QUICKSTART.md). Copy this file onto the demo board (it runs
MicroPython) and execute it. It:

  1. selects this project and clocks it at 25 MHz,
  2. receives the project's 115200-baud UART stream from `uo[0]` using a PIO
     state machine (any GPIO can be a UART RX that way),
  3. measures the ring-oscillator frequency `Fd` on `uio[1]` with a second PIO
     state machine (this is the number you cannot get any other way),
  4. writes `capture.bin` and prints `Fd`, so you can send both back.

    >>> import demoboard_capture as c
    >>> c.run(seconds=120)

⚠️ UNTESTED ON HARDWARE. Written before the chips exist (they arrive ~2027-05),
so treat it as a starting point, not a guarantee: the PIO programs are standard
patterns but nobody has run them against this chip yet. If something does not
work, the fallback is `capture.py` with a USB-UART adapter, and please open an
issue — fixing this script is genuinely useful to everyone.
"""

PROJECT = "tt_um_randomuzbek_charinst"
BAUD = 115200
CLOCK_HZ = 25_000_000

try:
    import rp2
    from machine import Pin
except ImportError:  # running on a PC, e.g. for linting
    rp2 = None
    Pin = None


# ---------------------------------------------------------------- PIO: UART RX
# Canonical MicroPython PIO UART receiver: sample in the middle of each bit,
# 8 state-machine cycles per bit, LSB first, 8N1.
if rp2:

    @rp2.asm_pio(
        autopush=True,
        push_thresh=8,
        in_shiftdir=rp2.PIO.SHIFT_RIGHT,
        fifo_join=rp2.PIO.JOIN_RX,
    )
    def uart_rx():
        label("start")
        wait(0, pin, 0)                 # falling edge = start bit
        set(x, 7)[10]                   # 8 data bits; land in the middle of bit 0
        label("bitloop")
        in_(pins, 1)
        jmp(x_dec, "bitloop")[6]
        wait(1, pin, 0)                 # stop bit
        jmp("start")

    # ------------------------------------------------- PIO: period measurement
    # After a rising edge, count loop iterations until the next rising edge.
    # Each iteration is 2 instructions, so period_cycles = 2 * count and
    #   f_in = sm_freq / (2 * count)
    @rp2.asm_pio()
    def period_counter():
        wrap_target()
        wait(0, pin, 0)
        wait(1, pin, 0)                 # rising edge: start of period
        mov(x, invert(null))            # x = 0xFFFFFFFF
        label("high")
        jmp(x_dec, "high_chk")
        label("high_chk")
        jmp(pin, "high")                # still high -> keep counting
        label("low")
        jmp(x_dec, "low_chk")
        label("low_chk")
        jmp(pin, "done")                # high again -> period complete
        jmp("low")
        label("done")
        mov(isr, invert(x))             # count = ~x
        push()
        wrap()


def _pin_of(port_bit):
    """Best-effort: get the machine.Pin behind a DemoBoard port bit."""
    for attr in ("raw_pin", "pin", "_pin"):
        p = getattr(port_bit, attr, None)
        if p is not None:
            return p() if callable(p) else p
    if isinstance(port_bit, Pin):
        return port_bit
    raise RuntimeError(
        "Could not find the GPIO behind this port bit. Pass the GPIO number "
        "explicitly: run(uo0_gpio=..., uio1_gpio=...). Print `dir(tt.uo_out[0])` "
        "to discover the attribute name on your firmware version."
    )


def measure_fd(uio1_gpio, sm_freq=125_000_000, samples=32):
    """Measure the divided ring-oscillator frequency on uio[1], in Hz."""
    pin = Pin(uio1_gpio, Pin.IN)
    sm = rp2.StateMachine(4, period_counter, freq=sm_freq, in_base=pin, jmp_pin=pin)
    sm.active(1)
    counts = []
    try:
        for _ in range(samples):
            counts.append(sm.get())
    finally:
        sm.active(0)
    counts.sort()
    median = counts[len(counts) // 2]
    if median == 0:
        return None
    return sm_freq / (2.0 * median)


def run(seconds=120, out="capture.bin", ro_div=3, dut_sel=0,
        uo0_gpio=None, uio1_gpio=None):
    """Select the project, run a sweep, record the stream, measure Fd."""
    from ttboard.demoboard import DemoBoard

    tt = DemoBoard.get()
    tt.shuttle.__getattr__(PROJECT).enable()
    print("project enabled:", PROJECT)

    if uo0_gpio is None:
        uo0_gpio = _pin_of(tt.uo_out[0])
    if uio1_gpio is None:
        uio1_gpio = _pin_of(tt.uio_out[1])
    uo0 = uo0_gpio if isinstance(uo0_gpio, Pin) else Pin(uo0_gpio, Pin.IN)

    # UART receiver on uo[0], 8 SM cycles per bit.
    rx = rp2.StateMachine(0, uart_rx, freq=8 * BAUD, in_base=uo0, jmp_pin=uo0)
    rx.active(1)

    tt.reset_project(True)
    tt.ui_in.value = ((dut_sel & 0x3) << 5) | ((ro_div & 0x7) << 2)
    tt.clock_project_PWM(CLOCK_HZ)
    tt.reset_project(False)

    # start pulse on ui[0]
    tt.ui_in[0] = 1
    tt.ui_in[0] = 0
    print("sweep started; busy =", bool(tt.uo_out[1]))

    fd = None
    try:
        fd = measure_fd(uio1_gpio if not isinstance(uio1_gpio, Pin) else uio1_gpio.id())
    except Exception as exc:            # measurement is optional, capture is not
        print("Fd measurement failed (continuing):", exc)
    if fd:
        print("MEASURED Fd = %.1f Hz (%.3f MHz), ro_div=%d" % (fd, fd / 1e6, ro_div))
    else:
        print("Fd not measured — tau still works, W will not be absolute")

    import time
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    total = 0
    with open(out, "wb") as fh:
        buf = bytearray(64)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            n = 0
            while rx.rx_fifo() and n < len(buf):
                buf[n] = rx.get() >> 24      # PIO right-shifts into the MSB
                n += 1
            if n:
                fh.write(buf[:n])
                total += n
            else:
                time.sleep_ms(5)
    rx.active(0)
    tt.clock_project_stop()

    print("wrote %d bytes to %s (~%d frames)" % (total, out, total // 14))
    print("\nSend us: %s, the measured Fd above, ro_div=%d, dut_sel=%d,"
          % (out, ro_div, dut_sel))
    print("and the ambient temperature if you know it.")
    return {"bytes": total, "fd_hz": fd, "ro_div": ro_div, "dut_sel": dut_sel}
