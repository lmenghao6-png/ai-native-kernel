#pragma once
#include <stdint.h>
#define ELF_MAGIC 0x464C457F
typedef struct { uint8_t e_ident[16]; uint16_t e_type,e_machine; uint32_t e_version; uint64_t e_entry,e_phoff,e_shoff; uint32_t e_flags; uint16_t e_ehsize,e_phentsize,e_phnum,e_shentsize,e_shnum,e_shstrndx; } __attribute__((packed)) elf64_ehdr_t;
typedef struct { uint32_t p_type,p_flags; uint64_t p_offset,p_vaddr,p_paddr,p_filesz,p_memsz,p_align; } __attribute__((packed)) elf64_phdr_t;
#define PT_LOAD 1
#define PF_X 1
#define PF_W 2
#define PF_R 4
int elf_load(const char *p, uint64_t *e);
