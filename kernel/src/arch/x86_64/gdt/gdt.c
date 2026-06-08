#include "kernel/gdt.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stdint.h>

struct gdt_ptr {
    uint16_t limit;
    uint64_t base;
} __attribute__((packed));

struct tss {
    uint32_t reserved0;
    uint64_t rsp[3];
    uint64_t ist[8];
    uint64_t reserved1;
    uint16_t reserved2;
    uint16_t iomap_base;
} __attribute__((packed));

static uint64_t gdt[7];
static struct gdt_ptr gp;
static struct tss tss;
static uint8_t kernel_stack[16384] __attribute__((aligned(16)));
static uint8_t ist_stack[4096] __attribute__((aligned(16)));

static void gdt_set_tss(int index, uint64_t base, uint32_t limit) {
    gdt[index] =
        (limit & 0xFFFFULL) |
        ((base & 0xFFFFFFULL) << 16) |
        (UINT64_C(0x89) << 40) |
        (((uint64_t)limit & 0xF0000ULL) << 32) |
        ((base & UINT64_C(0xFF000000)) << 32);
    gdt[index + 1] = base >> 32;
}

void gdt_init(void) {
    memset(gdt, 0, sizeof(gdt));
    memset(&tss, 0, sizeof(tss));

    gdt[1] = UINT64_C(0x00AF9A000000FFFF);
    gdt[2] = UINT64_C(0x00CF92000000FFFF);
    gdt[3] = UINT64_C(0x00AFFA000000FFFF);
    gdt[4] = UINT64_C(0x00CFF2000000FFFF);
    gdt_set_tss(5, (uint64_t)&tss, sizeof(tss) - 1);

    tss.rsp[0] = (uint64_t)kernel_stack + sizeof(kernel_stack);
    tss.ist[1] = (uint64_t)ist_stack + sizeof(ist_stack);
    tss.iomap_base = sizeof(tss);

    gp.limit = sizeof(gdt) - 1;
    gp.base = (uint64_t)&gdt;
    __asm__ volatile("lgdt (%0)" : : "r"(&gp));
    __asm__ volatile(
        "movw $0x10, %%ax;"
        "movw %%ax, %%ds;"
        "movw %%ax, %%es;"
        "movw %%ax, %%fs;"
        "movw %%ax, %%gs;"
        "movw %%ax, %%ss"
        :
        :
        : "ax"
    );
}

void gdt_load_tss(void) {
    __asm__ volatile("ltr %%ax" : : "a"(GDT_TSS));
    serial_write("[gdt] TSS loaded\n");
}
