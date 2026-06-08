#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include "limine.h"

#define PMM_PAGE_SIZE 4096ULL
#define PMM_BITMAP_BYTES 131072ULL
#define PMM_MAX_PAGES (PMM_BITMAP_BYTES * 8)

static uint8_t bitmap[PMM_BITMAP_BYTES];
static uint64_t total_pages = 0;
static uint64_t free_pages = 0;
static uint64_t highest_page = 0;

static void set_page_state(uint64_t page, bool allocated) {
    if (page >= PMM_MAX_PAGES) {
        return;
    }

    uint8_t mask = (uint8_t)(1U << (page % 8));
    if (allocated) {
        bitmap[page / 8] |= mask;
    } else {
        bitmap[page / 8] &= (uint8_t)~mask;
    }
}

bool pmm_init(const struct limine_memmap_response *memmap) {
    memset(bitmap, 0xFF, sizeof(bitmap));
    total_pages = 0;
    free_pages = 0;
    highest_page = 0;

    if (!memmap || !memmap->entries) {
        serial_write("[pmm] missing Limine memory map\n");
        return false;
    }

    for (uint64_t i = 0; i < memmap->entry_count; i++) {
        const struct limine_memmap_entry *entry = memmap->entries[i];
        if (!entry || entry->type != LIMINE_MEMMAP_USABLE) {
            continue;
        }

        uint64_t start = (entry->base + PMM_PAGE_SIZE - 1) / PMM_PAGE_SIZE;
        uint64_t end = (entry->base + entry->length) / PMM_PAGE_SIZE;
        if (end > PMM_MAX_PAGES) {
            end = PMM_MAX_PAGES;
        }

        for (uint64_t page = start; page < end; page++) {
            set_page_state(page, false);
            total_pages++;
            free_pages++;
        }

        if (end > highest_page) {
            highest_page = end;
        }
    }

    /* Physical address zero remains the allocation failure sentinel. */
    if ((bitmap[0] & 1U) == 0) {
        set_page_state(0, true);
        free_pages--;
    }

    if (free_pages == 0) {
        serial_write("[pmm] no usable pages\n");
        return false;
    }

    serial_write("[pmm] usable pages: ");
    serial_write_u64(free_pages);
    serial_write("\n");
    return true;
}

uint64_t pmm_alloc(void) {
    if (free_pages == 0) {
        return 0;
    }

    uint64_t bytes = (highest_page + 7) / 8;
    for (uint64_t i = 0; i < bytes; i++) {
        if (bitmap[i] == 0xFF) {
            continue;
        }
        for (uint8_t bit = 0; bit < 8; bit++) {
            uint8_t mask = (uint8_t)(1U << bit);
            if ((bitmap[i] & mask) == 0) {
                bitmap[i] |= mask;
                free_pages--;
                return (i * 8 + bit) * PMM_PAGE_SIZE;
            }
        }
    }
    return 0;
}

pmm_stats_t pmm_get_stats(void) {
    pmm_stats_t stats = {
        .total_pages = total_pages,
        .free_pages = free_pages,
        .highest_page = highest_page,
    };
    return stats;
}
