#include "kernel/gdt.h"
#include "kernel/serial.h"
#include "kernel/kheap.h"
#include <stdint.h>
struct gdt_entry { uint16_t limit_low; uint16_t base_low; uint8_t base_mid; uint8_t access; uint8_t gran; uint8_t base_high; } __attribute__((packed));
struct gdt_ptr { uint16_t limit; uint64_t base; } __attribute__((packed));
struct tss { uint32_t reserved0; uint64_t rsp[3]; uint64_t ist[8]; uint64_t reserved1; uint16_t reserved2; uint16_t iomap_base; } __attribute__((packed));
static struct gdt_entry gdt[7];
static struct gdt_ptr gp;
static struct tss tss;
static uint8_t tss_stack[4096] __attribute__((aligned(16)));

static void gdt_set(int n, uint32_t base, uint32_t limit, uint8_t access, uint8_t gran) {
    gdt[n].base_low = base & 0xFFFF; gdt[n].base_mid = (base >> 16) & 0xFF; gdt[n].base_high = (base >> 24) & 0xFF;
    gdt[n].limit_low = limit & 0xFFFF; gdt[n].gran = ((limit >> 16) & 0x0F) | (gran & 0xF0);
    gdt[n].access = access;
}
void gdt_init(void) {
    gdt_set(0,0,0,0,0); gdt_set(1,0,0xFFFFF,0x9A,0xA0); gdt_set(2,0,0xFFFFF,0x92,0xA0);
    gdt_set(3,0,0xFFFFF,0xFA,0xA0); gdt_set(4,0,0xFFFFF,0xF2,0xA0);
    gdt_set(5,(uint32_t)(uint64_t)&tss,sizeof(tss)-1,0x89,0x00);
    gp.limit = sizeof(gdt)-1; gp.base = (uint64_t)&gdt;
    __asm__ volatile("lgdt (%0)" : : "r"(&gp));
    __asm__ volatile("movw $0x10, %%ax; movw %%ax, %%ds; movw %%ax, %%es; movw %%ax, %%fs; movw %%ax, %%gs; movw %%ax, %%ss" : : : "ax");
    uint64_t tss_base = (uint64_t)&tss;
    gdt[5].base_low = tss_base & 0xFFFF; gdt[5].base_mid = (tss_base>>16)&0xFF; gdt[5].base_high = (tss_base>>24)&0xFF;
    gdt_set(5,(uint32_t)tss_base,sizeof(tss)-1,0x89,0x00);
    for(int i=0;i<sizeof(tss);i++) ((uint8_t*)&tss)[i]=0;
    tss.ist[1]=(uint64_t)tss_stack+sizeof(tss_stack);
}
void gdt_load_tss(void) {
    uint64_t rsp0 = (uint64_t)kmalloc(0x4000) + 0x4000;
    tss.rsp[0] = rsp0;
    __asm__ volatile("ltr %%ax" : : "a"(GDT_TSS));
}
