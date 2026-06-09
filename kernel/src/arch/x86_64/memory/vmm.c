#include "kernel/vmm.h"
#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stdint.h>

#define PAGE_PRESENT 1ULL
#define PAGE_HUGE (1ULL << 7)
#define USER_REGION_BASE 0x0000008000000000ULL
#define USER_REGION_LIMIT 0x0000800000000000ULL
#define KERNEL_REGION_BASE 0xffffff0000000000ULL

struct table_allocation {
    uint64_t *parent_entry;
    uint64_t physical_address;
};

static uint64_t hhdm = 0;
static uint64_t boot_cr3 = 0;
static uint64_t owned_cr3 = 0;
static uint64_t kernel_next = 0;
static uint64_t user_next = 0;
static uint64_t mapped_count = 0;
static uint8_t owned_table_bitmap[PMM_BITMAP_BYTES];

static bool is_canonical(uint64_t address) {
    uint64_t upper = address >> 48;
    return upper == 0 || upper == 0xFFFF;
}

static uint64_t table_flags(uint64_t page_flags) {
    return VMM_PAGE_WRITABLE |
        (page_flags & VMM_PAGE_USER) |
        PAGE_PRESENT;
}

static bool table_is_owned(uint64_t physical_address) {
    uint64_t page = physical_address / PMM_PAGE_SIZE;
    if (page >= PMM_MAX_PAGES) {
        return false;
    }
    return (owned_table_bitmap[page / 8] &
        (uint8_t)(1U << (page % 8))) != 0;
}

static void set_table_owned(uint64_t physical_address, bool owned) {
    uint64_t page = physical_address / PMM_PAGE_SIZE;
    if (page >= PMM_MAX_PAGES) {
        return;
    }

    uint8_t mask = (uint8_t)(1U << (page % 8));
    if (owned) {
        owned_table_bitmap[page / 8] |= mask;
    } else {
        owned_table_bitmap[page / 8] &= (uint8_t)~mask;
    }
}

static bool table_is_empty(const uint64_t *table) {
    for (uint64_t i = 0; i < 512; i++) {
        if (table[i] & PAGE_PRESENT) {
            return false;
        }
    }
    return true;
}

static void rollback_table_allocations(
    struct table_allocation *allocations,
    uint64_t count
) {
    while (count > 0) {
        count--;
        *allocations[count].parent_entry = 0;
        set_table_owned(allocations[count].physical_address, false);
        pmm_free(allocations[count].physical_address);
    }
}

static uint64_t *get_next_table(
    uint64_t *entry,
    uint64_t flags,
    struct table_allocation *allocations,
    uint64_t *allocation_count
) {
    if (*entry & PAGE_PRESENT) {
        if (*entry & PAGE_HUGE) {
            return 0;
        }
        *entry |= VMM_PAGE_WRITABLE | (flags & VMM_PAGE_USER);
        return (uint64_t *)((*entry & ~(PMM_PAGE_SIZE - 1)) + hhdm);
    }

    uint64_t physical_address = pmm_alloc();
    if (!physical_address) {
        return 0;
    }

    uint64_t *table = (uint64_t *)(physical_address + hhdm);
    memset(table, 0, PMM_PAGE_SIZE);
    *entry = physical_address | table_flags(flags);
    set_table_owned(physical_address, true);

    allocations[*allocation_count].parent_entry = entry;
    allocations[*allocation_count].physical_address = physical_address;
    (*allocation_count)++;
    return table;
}

static bool find_leaf_entry(
    uint64_t virtual_address,
    uint64_t flags,
    bool create,
    uint64_t **leaf_out,
    struct table_allocation *allocations,
    uint64_t *allocation_count
) {
    uint64_t *pml4 = (uint64_t *)(owned_cr3 + hhdm);
    uint64_t *pml4e = &pml4[(virtual_address >> 39) & 0x1FF];
    uint64_t *pdpt;

    if (create) {
        pdpt = get_next_table(
            pml4e,
            flags,
            allocations,
            allocation_count
        );
    } else {
        if (!(*pml4e & PAGE_PRESENT) || (*pml4e & PAGE_HUGE)) {
            return false;
        }
        pdpt = (uint64_t *)((*pml4e & ~(PMM_PAGE_SIZE - 1)) + hhdm);
    }
    if (!pdpt) {
        return false;
    }

    uint64_t *pdpte = &pdpt[(virtual_address >> 30) & 0x1FF];
    uint64_t *pd;
    if (create) {
        pd = get_next_table(
            pdpte,
            flags,
            allocations,
            allocation_count
        );
    } else {
        if (!(*pdpte & PAGE_PRESENT) || (*pdpte & PAGE_HUGE)) {
            return false;
        }
        pd = (uint64_t *)((*pdpte & ~(PMM_PAGE_SIZE - 1)) + hhdm);
    }
    if (!pd) {
        return false;
    }

    uint64_t *pde = &pd[(virtual_address >> 21) & 0x1FF];
    uint64_t *pt;
    if (create) {
        pt = get_next_table(
            pde,
            flags,
            allocations,
            allocation_count
        );
    } else {
        if (!(*pde & PAGE_PRESENT) || (*pde & PAGE_HUGE)) {
            return false;
        }
        pt = (uint64_t *)((*pde & ~(PMM_PAGE_SIZE - 1)) + hhdm);
    }
    if (!pt) {
        return false;
    }

    *leaf_out = &pt[(virtual_address >> 12) & 0x1FF];
    return true;
}

static bool reclaim_empty_table(
    uint64_t *parent_entry,
    uint64_t physical_address,
    uint64_t *table
) {
    if (!table_is_owned(physical_address) || !table_is_empty(table)) {
        return false;
    }

    uint64_t old_entry = *parent_entry;
    *parent_entry = 0;
    if (!pmm_free(physical_address)) {
        *parent_entry = old_entry;
        return false;
    }
    set_table_owned(physical_address, false);
    return true;
}

bool vmm_init(uint64_t offset) {
    if (!offset) {
        serial_write("[vmm] missing HHDM offset\n");
        return false;
    }

    hhdm = offset;
    memset(owned_table_bitmap, 0, sizeof(owned_table_bitmap));
    mapped_count = 0;
    __asm__ volatile("mov %%cr3, %0" : "=r"(boot_cr3));
    owned_cr3 = pmm_alloc();
    if (!owned_cr3) {
        serial_write("[vmm] failed to allocate CR3\n");
        return false;
    }

    memset((void *)(owned_cr3 + hhdm), 0, PMM_PAGE_SIZE);
    uint64_t *source = (uint64_t *)(boot_cr3 + hhdm);
    uint64_t *destination = (uint64_t *)(owned_cr3 + hhdm);
    for (uint64_t i = 0; i < 512; i++) {
        destination[i] = source[i];
    }
    __asm__ volatile("mov %0, %%cr3" : : "r"(owned_cr3) : "memory");

    kernel_next = KERNEL_REGION_BASE;
    user_next = USER_REGION_BASE;
    serial_write("[vmm] init done\n");
    return true;
}

bool vmm_map_new_pages(
    uint64_t virtual_address,
    uint64_t count,
    uint64_t flags,
    uint64_t *physical_address_out
) {
    if (physical_address_out) {
        *physical_address_out = 0;
    }
    if (!owned_cr3 ||
        !hhdm ||
        count == 0 ||
        (virtual_address & (PMM_PAGE_SIZE - 1)) != 0 ||
        count > (UINT64_MAX - virtual_address) / PMM_PAGE_SIZE ||
        !is_canonical(virtual_address) ||
        !is_canonical(virtual_address + count * PMM_PAGE_SIZE - 1)) {
        return false;
    }

    uint64_t mapped = 0;
    uint64_t first_physical_address = 0;
    for (; mapped < count; mapped++) {
        uint64_t physical_address = pmm_alloc();
        if (!physical_address) {
            break;
        }
        memset((void *)(physical_address + hhdm), 0, PMM_PAGE_SIZE);

        uint64_t current_virtual =
            virtual_address + mapped * PMM_PAGE_SIZE;
        if (!vmm_map_at(current_virtual, physical_address, flags)) {
            pmm_free(physical_address);
            break;
        }
        if (mapped == 0) {
            first_physical_address = physical_address;
        }
    }

    if (mapped != count) {
        while (mapped > 0) {
            mapped--;
            vmm_unmap_page(
                virtual_address + mapped * PMM_PAGE_SIZE,
                true
            );
        }
        return false;
    }

    if (physical_address_out) {
        *physical_address_out = first_physical_address;
    }
    return true;
}

bool vmm_alloc_user_pages(
    uint64_t count,
    uint64_t flags,
    uint64_t *virtual_address_out,
    uint64_t *physical_address_out
) {
    if (virtual_address_out) {
        *virtual_address_out = 0;
    }
    if (physical_address_out) {
        *physical_address_out = 0;
    }
    if (count == 0 ||
        count > (USER_REGION_LIMIT - user_next) / PMM_PAGE_SIZE) {
        return false;
    }

    uint64_t virtual_address = user_next;
    if (!vmm_map_new_pages(
            virtual_address,
            count,
            flags | VMM_PAGE_USER,
            physical_address_out)) {
        return false;
    }

    user_next += count * PMM_PAGE_SIZE;
    if (virtual_address_out) {
        *virtual_address_out = virtual_address;
    }
    return true;
}

bool vmm_map_at(
    uint64_t virtual_address,
    uint64_t physical_address,
    uint64_t flags
) {
    if (!owned_cr3 ||
        (virtual_address & (PMM_PAGE_SIZE - 1)) != 0 ||
        physical_address == 0 ||
        (physical_address & (PMM_PAGE_SIZE - 1)) != 0 ||
        !is_canonical(virtual_address)) {
        return false;
    }

    struct table_allocation allocations[3];
    uint64_t allocation_count = 0;
    uint64_t *leaf = 0;
    if (!find_leaf_entry(
            virtual_address,
            flags,
            true,
            &leaf,
            allocations,
            &allocation_count) ||
        (*leaf & PAGE_PRESENT)) {
        rollback_table_allocations(allocations, allocation_count);
        return false;
    }

    *leaf = (physical_address & ~(PMM_PAGE_SIZE - 1)) |
        (flags & 0xFFF) |
        PAGE_PRESENT;
    mapped_count++;
    __asm__ volatile(
        "invlpg (%0)"
        :
        : "r"(virtual_address)
        : "memory"
    );
    return true;
}

bool vmm_unmap_page(uint64_t virtual_address, bool free_physical) {
    if (!owned_cr3 ||
        (virtual_address & (PMM_PAGE_SIZE - 1)) != 0 ||
        !is_canonical(virtual_address)) {
        return false;
    }

    uint64_t *pml4 = (uint64_t *)(owned_cr3 + hhdm);
    uint64_t *pml4e = &pml4[(virtual_address >> 39) & 0x1FF];
    if (!(*pml4e & PAGE_PRESENT) || (*pml4e & PAGE_HUGE)) {
        return false;
    }

    uint64_t pdpt_physical = *pml4e & ~(PMM_PAGE_SIZE - 1);
    uint64_t *pdpt = (uint64_t *)(pdpt_physical + hhdm);
    uint64_t *pdpte = &pdpt[(virtual_address >> 30) & 0x1FF];
    if (!(*pdpte & PAGE_PRESENT) || (*pdpte & PAGE_HUGE)) {
        return false;
    }

    uint64_t pd_physical = *pdpte & ~(PMM_PAGE_SIZE - 1);
    uint64_t *pd = (uint64_t *)(pd_physical + hhdm);
    uint64_t *pde = &pd[(virtual_address >> 21) & 0x1FF];
    if (!(*pde & PAGE_PRESENT) || (*pde & PAGE_HUGE)) {
        return false;
    }

    uint64_t pt_physical = *pde & ~(PMM_PAGE_SIZE - 1);
    uint64_t *pt = (uint64_t *)(pt_physical + hhdm);
    uint64_t *pte = &pt[(virtual_address >> 12) & 0x1FF];
    if (!(*pte & PAGE_PRESENT)) {
        return false;
    }

    uint64_t mapped_physical = *pte & ~(PMM_PAGE_SIZE - 1);
    *pte = 0;
    if (mapped_count > 0) {
        mapped_count--;
    }
    __asm__ volatile(
        "invlpg (%0)"
        :
        : "r"(virtual_address)
        : "memory"
    );

    bool released = !free_physical || pmm_free(mapped_physical);
    if (reclaim_empty_table(pde, pt_physical, pt) &&
        reclaim_empty_table(pdpte, pd_physical, pd)) {
        reclaim_empty_table(pml4e, pdpt_physical, pdpt);
    }
    return released;
}

bool vmm_self_test(void) {
    const uint64_t base = USER_REGION_BASE;
    pmm_stats_t pmm_before = pmm_get_stats();
    uint64_t mapped_before = mapped_count;

    if (!vmm_map_new_pages(base + PMM_PAGE_SIZE, 1, VMM_PAGE_USER, 0)) {
        serial_write("[vmm] rollback self-test failed\n");
        return false;
    }

    pmm_stats_t after_guard = pmm_get_stats();
    bool rejected_overlap =
        !vmm_map_new_pages(base, 2, VMM_PAGE_USER, 0);
    pmm_stats_t after_rollback = pmm_get_stats();
    bool rollback_clean =
        after_rollback.free_pages == after_guard.free_pages &&
        mapped_count == mapped_before + 1;
    bool cleanup_ok =
        vmm_unmap_page(base + PMM_PAGE_SIZE, true);
    pmm_stats_t after_cleanup = pmm_get_stats();

    bool passed = rejected_overlap &&
        rollback_clean &&
        cleanup_ok &&
        after_cleanup.free_pages == pmm_before.free_pages &&
        mapped_count == mapped_before;
    serial_write(passed
        ? "[vmm] rollback self-test passed\n"
        : "[vmm] rollback self-test failed\n");
    return passed;
}

const vmm_stats_t *vmm_get_stats(void) {
    static vmm_stats_t stats;
    stats.hhdm_offset = hhdm;
    stats.boot_cr3 = boot_cr3;
    stats.owned_cr3 = owned_cr3;
    stats.kernel_region_base = KERNEL_REGION_BASE;
    stats.kernel_next_free_virtual = kernel_next;
    stats.user_region_base = USER_REGION_BASE;
    stats.user_next_free_virtual = user_next;
    stats.mapped_pages = mapped_count;
    return &stats;
}
