#include "kernel/serial.h"
#include "kernel/x86_64/io.h"
#define COM1 0x3F8
void serial_init(void) {
    outb(COM1 + 1, 0x00); outb(COM1 + 3, 0x80); outb(COM1 + 0, 0x03);
    outb(COM1 + 1, 0x00); outb(COM1 + 3, 0x03); outb(COM1 + 2, 0xC7); outb(COM1 + 4, 0x0B);
}
static int serial_is_transmit_empty(void) { return inb(COM1 + 5) & 0x20; }
static int serial_received(void) { return inb(COM1 + 5) & 1; }
void serial_write_char(char ch) { while (!serial_is_transmit_empty()); outb(COM1, ch); }
void serial_write(const char *text) { while (*text) serial_write_char(*text++); }
void serial_write_hex_u64(uint64_t value) {
    serial_write("0x");
    for (int i = 60; i >= 0; i -= 4) {
        uint8_t nibble = (value >> i) & 0xF;
        serial_write_char(nibble < 10 ? '0' + nibble : 'a' + nibble - 10);
    }
}
void serial_write_u64(uint64_t value) {
    char buf[21]; int i = 20; buf[20] = 0;
    if (value == 0) { serial_write("0"); return; }
    while (value > 0) { buf[--i] = '0' + (value % 10); value /= 10; }
    serial_write(&buf[i]);
}
int serial_try_read(void) { return serial_received() ? inb(COM1) : -1; }
