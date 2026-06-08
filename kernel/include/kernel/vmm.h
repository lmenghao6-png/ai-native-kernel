#pragma once
#include <stdint.h>
#include <stdbool.h>
enum vmm_page_flags { VMM_PAGE_WRITABLE = 2, VMM_PAGE_USER = 4 };
void vmm_init(uint64_t hhdm_offset);
bool vmm_map_new_pages(uint64_t va, uint64_t count, uint64_t flags, uint64_t *pa_out);
bool vmm_alloc_user_pages(uint64_t count, uint64_t flags, uint64_t *va_out, uint64_t *pa_out);
bool vmm_map_at(uint64_t va, uint64_t pa, uint64_t flags);
