#include "kernel/idt.h"
#include <stdint.h>
struct idt_entry { uint16_t offset_low; uint16_t selector; uint8_t ist; uint8_t flags; uint16_t offset_mid; uint32_t offset_high; uint32_t reserved; } __attribute__((packed));
struct idt_ptr { uint16_t limit; uint64_t base; } __attribute__((packed));
static struct idt_entry idt[256];
extern void *isr_stub_table[];
void idt_init(void) {
    for(int i=0;i<256;i++) {
        uint64_t addr = (uint64_t)isr_stub_table[i];
        idt[i].offset_low = addr & 0xFFFF; idt[i].offset_mid = (addr>>16)&0xFFFF; idt[i].offset_high = addr>>32;
        idt[i].selector = 0x08; idt[i].ist = (i==8) ? 1 : 0;
        idt[i].flags = 0x8E; idt[i].reserved = 0;
        if (i==0x80) { idt[i].flags = 0xEE; idt[i].ist = 0; }
    }
    struct idt_ptr ptr = { .limit = sizeof(idt)-1, .base = (uint64_t)&idt };
    __asm__ volatile("lidt (%0)" : : "r"(&ptr));
}
