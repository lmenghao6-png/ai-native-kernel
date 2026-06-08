#pragma once
#include <stdint.h>
#define GDT_KERNEL_CODE 0x08
#define GDT_USER_CODE 0x18
#define GDT_USER_DATA 0x20
#define GDT_TSS 0x28
void gdt_init(void);
void gdt_load_tss(void);
