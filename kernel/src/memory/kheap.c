#include "kernel/kheap.h"
#include "kernel/vmm.h"
#include "kernel/serial.h"
static uint64_t heap_base = 0, heap_used = 0, heap_size = 0x400000;
void kheap_init(void) {
    uint64_t pa = 0;
    vmm_map_new_pages(0xffffff0000001000, heap_size/0x1000, 0, &pa);
    heap_base = 0xffffff0000001000;
    heap_used = 0;
    serial_write("[kheap] ready\n");
}
void *kmalloc(uint64_t size) {
    size = (size + 15) & ~15ULL;
    if (heap_used + size > heap_size) return 0;
    void *p = (void *)(heap_base + heap_used);
    heap_used += size;
    return p;
}
void *kzalloc(uint64_t size) {
    void *p = kmalloc(size);
    if (p) for (uint64_t i=0;i<size;i++) ((uint8_t*)p)[i]=0;
    return p;
}
