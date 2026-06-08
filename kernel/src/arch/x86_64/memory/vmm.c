#include "kernel/vmm.h"
#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stdint.h>

static uint64_t hhdm = 0, boot_cr3 = 0, owned_cr3 = 0;
static uint64_t kernel_next = 0, user_next = 0;
static uint64_t mapped_count = 0;

static inline uint64_t *pml4_entry(uint64_t cr3, uint64_t vaddr) {
    uint64_t *pml4 = (uint64_t *)(cr3 + hhdm);
    return &pml4[(vaddr >> 39) & 0x1FF];
}
static inline uint64_t *pdpt_entry(uint64_t *pml4e, uint64_t vaddr) {
    if (!(*pml4e & 1)) {
        uint64_t p = pmm_alloc(); if(!p) return 0;
        memset((void*)(p+hhdm),0,0x1000);
        *pml4e = p | 7;
    }
    uint64_t *pdpt = (uint64_t *)((*pml4e & ~0xFFFULL) + hhdm);
    return &pdpt[(vaddr >> 30) & 0x1FF];
}
static inline uint64_t *pd_entry(uint64_t *pdpte, uint64_t vaddr) {
    if (!(*pdpte & 1)) {
        uint64_t p = pmm_alloc(); if(!p) return 0;
        memset((void*)(p+hhdm),0,0x1000);
        *pdpte = p | 7;
    }
    uint64_t *pd = (uint64_t *)((*pdpte & ~0xFFFULL) + hhdm);
    return &pd[(vaddr >> 21) & 0x1FF];
}
static inline uint64_t *pt_entry(uint64_t *pde, uint64_t vaddr) {
    if (!(*pde & 1)) {
        uint64_t p = pmm_alloc(); if(!p) return 0;
        memset((void*)(p+hhdm),0,0x1000);
        *pde = p | 7;
    }
    uint64_t *pt = (uint64_t *)((*pde & ~0xFFFULL) + hhdm);
    return &pt[(vaddr >> 12) & 0x1FF];
}

void vmm_init(uint64_t offset) {
    hhdm = offset;
    __asm__ volatile("mov %%cr3, %0" : "=r"(boot_cr3));
    owned_cr3 = pmm_alloc();
    if (!owned_cr3) { serial_write("[vmm] failed to allocate CR3\n"); return; }
    memset((void*)(owned_cr3+hhdm), 0, 0x1000);
    uint64_t *src = (uint64_t*)(boot_cr3+hhdm), *dst = (uint64_t*)(owned_cr3+hhdm);
    for(int i=0;i<512;i++) dst[i] = src[i];
    __asm__ volatile("mov %0, %%cr3" : : "r"(owned_cr3));
    kernel_next = 0xffffff0000000000ULL;
    user_next = 0x0000008000000000ULL;
    serial_write("[vmm] init done\n");
}

bool vmm_map_new_pages(uint64_t va, uint64_t count, uint64_t flags, uint64_t *pa_out) {
    for (uint64_t i = 0; i < count; i++) {
        uint64_t pa = pmm_alloc();
        if (!pa) return false;
        uint64_t v = va + i * 0x1000;
        if (!vmm_map_at(v, pa, flags)) return false;
        if (pa_out && i == 0) *pa_out = pa;
    }
    mapped_count += count;
    return true;
}

bool vmm_alloc_user_pages(uint64_t count, uint64_t flags, uint64_t *va_out, uint64_t *pa_out) {
    uint64_t va = user_next;
    user_next += count * 0x1000;
    if (va_out) *va_out = va;
    return vmm_map_new_pages(va, count, flags | VMM_PAGE_USER, pa_out);
}

bool vmm_map_at(uint64_t va, uint64_t pa, uint64_t flags) {
    uint64_t *p4 = pml4_entry(owned_cr3, va);
    if (!p4) return false;
    uint64_t *p3 = pdpt_entry(p4, va);
    if (!p3) return false;
    uint64_t *p2 = pd_entry(p3, va);
    if (!p2) return false;
    uint64_t *p1 = pt_entry(p2, va);
    if (!p1) return false;
    *p1 = (pa & ~0xFFFULL) | (flags & 0xFFF) | 1;
    __asm__ volatile("invlpg (%0)" : : "r"(va) : "memory");
    return true;
}

const vmm_stats_t *vmm_get_stats(void) {
    static vmm_stats_t s;
    s.hhdm_offset = hhdm; s.boot_cr3 = boot_cr3; s.owned_cr3 = owned_cr3;
    s.kernel_region_base = 0xffffff0000000000ULL; s.kernel_next_free_virtual = kernel_next;
    s.user_region_base = 0x0000008000000000ULL; s.user_next_free_virtual = user_next;
    s.mapped_pages = mapped_count;
    return &s;
}
