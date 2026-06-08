OUTPUT_FORMAT(elf64-x86-64)
ENTRY(kmain)
PHDRS { limine_requests PT_LOAD; text PT_LOAD; rodata PT_LOAD; data PT_LOAD; initramfs PT_LOAD; }
SECTIONS {
    . = 0xffffffff80000000;
    .limine_requests : { KEEP(*(.limine_requests_start)) KEEP(*(.limine_requests)) KEEP(*(.limine_requests_end)) } :limine_requests
    . = ALIGN(0x1000);
    .text : { *(.text .text.*) } :text
    . = ALIGN(0x1000);
    .rodata : { *(.rodata .rodata.*) } :rodata
    . = ALIGN(0x1000);
    .data : { *(.data .data.*) } :data
    . = ALIGN(0x1000);
    .bss : { *(COMMON) *(.bss .bss.*) } :data
    . = ALIGN(0x1000);
    .initramfs : { _initramfs_start = .; KEEP(*(.initramfs)) _initramfs_end = .; } :initramfs
    /DISCARD/ : { *(.eh_frame) *(.note .note.*) }
}