#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include "limine.h"

static uint8_t allocated_bitmap[PMM_BITMAP_BYTES];
static uint8_t usable_bitmap[PMM_BITMAP_BYTES];
static uint64_t total_pages = 0;
static uint64_t free_pages = 0;
static uint64_t highest_page = 0;
static uint64_t allocation_hint = 1;

static bool bitmap_get(const uint8_t *map, uint64_t page) {
    return (map[page / 8] & (uint8_t)(1U << (page % 8))) != 0;
}

static void bitmap_set(uint8_t *map, uint64_t page, bool value) {
    uint8_t mask = (uint8_t)(1U << (page % 8));
    if (value) {
        map[page / 8] |= mask;
    } else {
        map[page / 8] &= (uint8_t)~mask;
    }
}

bool pmm_init(const struct limine_memmap_response *memmap) {
    memset(allocated_bitmap, 0xFF, sizeof(allocated_bitmap));
    memset(usable_bitmap, 0, sizeof(usable_bitmap));
    total_pages = 0;
    free_pages = 0;
    highest_page = 0;
    allocation_hint = 1;

    if (!memmap || !memmap->entries) {
        serial_write("[pmm] missing Limine memory map\n");
        return false;
    }

    for (uint64_t i = 0; i < memmap->entry_count; i++) {
        const struct limine_memmap_entry *entry = memmap->entries[i];
        if (!entry || entry->type != LIMINE_MEMMAP_USABLE) {
            continue;
        }

        uint64_t start = entry->base / PMM_PAGE_SIZE;
        if ((entry->base % PMM_PAGE_SIZE) != 0) {
            start++;
        }
        uint64_t end_address = entry->length > UINT64_MAX - entry->base
            ? UINT64_MAX
            : entry->base + entry->length;
        uint64_t end = end_address / PMM_PAGE_SIZE;
        if (end > PMM_MAX_PAGES) {
            end = PMM_MAX_PAGES;
        }

        for (uint64_t page = start; page < end; page++) {
            if (bitmap_get(usable_bitmap, page)) {
                continue;
            }
            bitmap_set(usable_bitmap, page, true);
            bitmap_set(allocated_bitmap, page, false);
            total_pages++;
            free_pages++;
        }

        if (end > highest_page) {
            highest_page = end;
        }
    }

    /* Physical address zero remains the allocation failure sentinel. */
    if (bitmap_get(usable_bitmap, 0) &&
        !bitmap_get(allocated_bitmap, 0)) {
        bitmap_set(allocated_bitmap, 0, true);
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

    for (uint64_t scanned = 0; scanned < highest_page; scanned++) {
        uint64_t page = allocation_hint + scanned;
        if (page >= highest_page) {
            page -= highest_page;
        }
        if (page == 0 ||
            !bitmap_get(usable_bitmap, page) ||
            bitmap_get(allocated_bitmap, page)) {
            continue;
        }

        bitmap_set(allocated_bitmap, page, true);
        free_pages--;
        allocation_hint = page + 1;
        if (allocation_hint >= highest_page) {
            allocation_hint = 1;
        }
        return page * PMM_PAGE_SIZE;
    }
    return 0;
}

bool pmm_free(uint64_t physical_address) {
    if (physical_address == 0 ||
        (physical_address & (PMM_PAGE_SIZE - 1)) != 0) {
        return false;
    }

    uint64_t page = physical_address / PMM_PAGE_SIZE;
    if (page >= highest_page ||
        !bitmap_get(usable_bitmap, page) ||
        !bitmap_get(allocated_bitmap, page)) {
        return false;
    }

    bitmap_set(allocated_bitmap, page, false);
    free_pages++;
    if (page < allocation_hint) {
        allocation_hint = page;
    }
    return true;
}

bool pmm_self_test(void) {
    pmm_stats_t before = pmm_get_stats();
    uint64_t first = pmm_alloc();
    uint64_t second = pmm_alloc();
    bool first_freed = first && pmm_free(first);
    bool double_free_rejected =
        first_freed && !pmm_free(first);

    if (!first || !second || !double_free_rejected) {
        if (first && !first_freed) {
            pmm_free(first);
        }
        if (second) {
            pmm_free(second);
        }
        serial_write("[pmm] self-test failed\n");
        return false;
    }

    uint64_t reused = pmm_alloc();
    bool reused_expected_page = reused == first;
    bool reused_freed = reused && pmm_free(reused);
    bool second_freed = pmm_free(second);
    pmm_stats_t after = pmm_get_stats();
    bool passed = reused_expected_page &&
        reused_freed &&
        second_freed &&
        after.free_pages == before.free_pages;

    serial_write(passed
        ? "[pmm] self-test passed\n"
        : "[pmm] self-test failed\n");
    return passed;
}

pmm_stats_t pmm_get_stats(void) {
    pmm_stats_t stats = {
        .total_pages = total_pages,
        .free_pages = free_pages,
        .highest_page = highest_page,
    };
    return stats;
}
