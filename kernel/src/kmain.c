#include <stdint.h>
#include "kernel/serial.h"
#include "kernel/gdt.h"
#include "kernel/idt.h"
#include "kernel/interrupt.h"
#include "kernel/pmm.h"
#include "kernel/vmm.h"
#include "kernel/kheap.h"
#include "kernel/uaccess.h"
#include "kernel/scheduler.h"
#include "kernel/task.h"
#include "kernel/debug_shell.h"
#include "kernel/vfs.h"
#include "kernel/initramfs.h"
#include "kernel/elf.h"
#include "limine.h"

__attribute__((used, section(".limine_requests")))
static volatile uint64_t base_revision[] = LIMINE_BASE_REVISION(3);

__attribute__((used, section(".limine_requests")))
static volatile struct limine_memmap_request memmap_req = {
    .id = LIMINE_MEMMAP_REQUEST_ID,
    .revision = 0,
    .response = 0,
};

__attribute__((used, section(".limine_requests")))
static volatile struct limine_hhdm_request hhdm_req = {
    .id = LIMINE_HHDM_REQUEST_ID,
    .revision = 0,
    .response = 0,
};

__attribute__((used, section(".limine_requests_start")))
static volatile uint64_t req_start[] = LIMINE_REQUESTS_START_MARKER;

__attribute__((used, section(".limine_requests_end")))
static volatile uint64_t req_end[] = LIMINE_REQUESTS_END_MARKER;

extern uint8_t _initramfs_start[], _initramfs_end[];

void kmain(void) {
    serial_init();
    serial_write("\n=== Bastion Kernel v0.3 ===\n\n");

    if (!LIMINE_BASE_REVISION_SUPPORTED(base_revision)) {
        serial_write("[boot] unsupported Limine base revision\n");
        for (;;) __asm__ volatile("hlt");
    }
    if (!memmap_req.response || !hhdm_req.response) {
        serial_write("[boot] missing required Limine responses\n");
        for (;;) __asm__ volatile("hlt");
    }

    gdt_init(); idt_init(); interrupt_init();
    if (!pmm_init(memmap_req.response)) {
        for (;;) __asm__ volatile("hlt");
    }
    if (!pmm_self_test()) {
        for (;;) __asm__ volatile("hlt");
    }
    if (!vmm_init(hhdm_req.response->offset)) {
        for (;;) __asm__ volatile("hlt");
    }
    if (!vmm_self_test()) {
        for (;;) __asm__ volatile("hlt");
    }
    kheap_init(); uaccess_init(); gdt_load_tss();
    scheduler_init(50); task_init(0);
    vfs_init();
    size_t isz = (size_t)(_initramfs_end - _initramfs_start);
    if (isz > 0 && isz < 33554432 && initramfs_load(_initramfs_start, isz)) {
        initramfs_dump();
    }
    else { serial_write("[initramfs] no archive\n"); }
    uint64_t entry = 0;
    if (elf_load("/bin/hello", &entry) == 0 && entry != 0) {
        serial_write("[kmain] ELF ready\n");
        if (task_prepare_ring3_demo(entry)) {
            task_enter_prepared();
        }
    }
    serial_write("\nbastion> "); debug_shell_run_forever();
}
