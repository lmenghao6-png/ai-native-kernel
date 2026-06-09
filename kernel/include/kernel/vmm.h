#pragma once
#include <stdint.h>
#include <stdbool.h>
enum vmm_page_flags { VMM_PAGE_WRITABLE = 2, VMM_PAGE_USER = 4 };
typedef struct { uint64_t hhdm_offset, boot_cr3, owned_cr3, kernel_region_base, kernel_next_free_virtual, user_region_base, user_next_free_virtual, reserved_kernel_pages, reserved_user_pages, mapped_pages; } vmm_stats_t;
bool vmm_init(uint64_t hhdm_offset);
bool vmm_map_new_pages(uint64_t va, uint64_t count, uint64_t flags, uint64_t *pa_out);
bool vmm_alloc_user_pages(uint64_t count, uint64_t flags, uint64_t *va_out, uint64_t *pa_out);
bool vmm_map_at(uint64_t va, uint64_t pa, uint64_t flags);
bool vmm_unmap_page(uint64_t va, bool free_physical);
bool vmm_self_test(void);
const vmm_stats_t *vmm_get_stats(void);
