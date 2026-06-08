#include "kernel/idt.h"
#include <stdint.h>
struct idt_entry { uint16_t offset_low; uint16_t selector; uint8_t ist; uint8_t flags; uint16_t offset_mid; uint32_t offset_high; uint32_t reserved; } __attribute__((packed));
struct idt_ptr { uint16_t limit; uint64_t base; } __attribute__((packed));
static struct idt_entry idt[256];
extern void *isr_stub_table[];
static void idt_set_gate(int vector, uint64_t address, uint8_t flags, uint8_t ist) {
    idt[vector].offset_low = address & 0xFFFF;
    idt[vector].offset_mid = (address >> 16) & 0xFFFF;
    idt[vector].offset_high = address >> 32;
    idt[vector].selector = 0x08;
    idt[vector].ist = ist;
    idt[vector].flags = flags;
    idt[vector].reserved = 0;
}
void idt_init(void) {
    for(int i=0;i<256;i++) {
        idt_set_gate(i, (uint64_t)isr_stub_table[0], 0x8E, 0);
    }
    for(int i=0;i<48;i++) {
        idt_set_gate(i, (uint64_t)isr_stub_table[i], 0x8E, i == 8 ? 1 : 0);
    }
    idt_set_gate(0x80, (uint64_t)isr_stub_table[48], 0xEE, 0);
    struct idt_ptr ptr = { .limit = sizeof(idt)-1, .base = (uint64_t)&idt };
    __asm__ volatile("lidt (%0)" : : "r"(&ptr));
}
