#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stddef.h>
typedef struct { uint64_t base; uint64_t length; uint32_t type; } limine_memmap_entry_t;
typedef struct { uint64_t revision; uint64_t entry_count; limine_memmap_entry_t **entries; } limine_memmap_response_t;
static uint8_t pmm_bitmap[131072];
static uint64_t pmm_total = 0, pmm_free = 0, pmm_hhdm = 0;
void pmm_init(void *response_ptr) {
    limine_memmap_response_t *resp = *(limine_memmap_response_t**)response_ptr;
    if (!resp) return;
    memset(pmm_bitmap, 0, sizeof(pmm_bitmap));
    for (uint64_t i = 0; i < resp->entry_count; i++) {
        limine_memmap_entry_t *e = resp->entries[i];
        if (e->type != 0) continue;
        for (uint64_t off = 0; off < e->length; off += 0x1000) {
            uint64_t pfn = (e->base + off) / 0x1000;
            if (pfn / 8 < sizeof(pmm_bitmap)) {
                pmm_bitmap[pfn / 8] |= (1 << (pfn % 8));
                pmm_total++; pmm_free++;
            }
        }
    }
    serial_write("[pmm] ready\n");
}
uint64_t pmm_alloc(void) {
    for (uint64_t i = 0; i < sizeof(pmm_bitmap); i++) {
        if (pmm_bitmap[i] == 0xFF) continue;
        for (int b = 0; b < 8; b++) {
            if (!(pmm_bitmap[i] & (1 << b))) {
                pmm_bitmap[i] |= (1 << b);
                pmm_free--;
                return (i * 8 + b) * 0x1000;
            }
        }
    }
    return 0;
}
uint64_t pmm_get_hhdm_offset(void) { return pmm_hhdm; }
pmm_stats_t pmm_get_stats(void) { pmm_stats_t s = {pmm_total, pmm_free}; return s; }
