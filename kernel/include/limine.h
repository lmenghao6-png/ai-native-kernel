#ifndef LIMINE_H
#define LIMINE_H
#include <stdint.h>

#define LIMINE_BASE_REVISION(N) static volatile uint64_t limine_base_revision_##N = N
#define LIMINE_REQUESTS_START_MARKER static volatile uint64_t limine_requests_start_marker[] = {0,0,0,0}
#define LIMINE_REQUESTS_END_MARKER static volatile uint64_t limine_requests_end_marker[] = {0,0,0,0}

#define LIMINE_MEMMAP_REQUEST UINT64_C(0x67cf3d9d378a806f)
#define LIMINE_HHDM_REQUEST UINT64_C(0x48dcf1cb8ad2b852)
#define LIMINE_KERNEL_ADDRESS_REQUEST UINT64_C(0x71ba76863cc55f63)
#define LIMINE_STACK_SIZE_REQUEST UINT64_C(0x224ef0460a8e8926)

struct limine_memmap_entry { uint64_t base; uint64_t length; uint64_t type; };
struct limine_memmap_response { uint64_t revision; uint64_t entry_count; struct limine_memmap_entry **entries; };
struct limine_memmap_request { uint64_t id[4]; uint64_t revision; struct limine_memmap_response *response; };

struct limine_hhdm_response { uint64_t revision; uint64_t offset; };
struct limine_hhdm_request { uint64_t id[4]; uint64_t revision; struct limine_hhdm_response *response; };

struct limine_kernel_address_response { uint64_t revision; uint64_t physical_base; uint64_t virtual_base; };
struct limine_kernel_address_request { uint64_t id[4]; uint64_t revision; struct limine_kernel_address_response *response; };

struct limine_stack_size_response { uint64_t revision; };
struct limine_stack_size_request { uint64_t id[4]; uint64_t revision; struct limine_stack_size_response *response; uint64_t stack_size; };

#endif
