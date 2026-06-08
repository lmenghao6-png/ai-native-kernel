.macro ISR_NOERR n
.global isr_stub_\n
isr_stub_\n:
    pushq $0
    pushq $\n
    jmp isr_common
.endm

.macro ISR_ERR n
.global isr_stub_\n
isr_stub_\n:
    pushq $\n
    jmp isr_common
.endm

ISR_NOERR 0;ISR_NOERR 1;ISR_NOERR 2;ISR_NOERR 3;ISR_NOERR 4;ISR_NOERR 5;ISR_NOERR 6;ISR_NOERR 7
ISR_ERR 8;ISR_NOERR 9;ISR_ERR 10;ISR_ERR 11;ISR_ERR 12;ISR_ERR 13;ISR_ERR 14
ISR_NOERR 15;ISR_NOERR 16;ISR_ERR 17;ISR_NOERR 18;ISR_NOERR 19;ISR_NOERR 20
ISR_NOERR 21;ISR_NOERR 22;ISR_NOERR 23;ISR_NOERR 24;ISR_NOERR 25;ISR_NOERR 26;ISR_NOERR 27
ISR_NOERR 28;ISR_NOERR 29;ISR_NOERR 30;ISR_NOERR 31

ISR_NOERR 32;ISR_NOERR 33;ISR_NOERR 34;ISR_NOERR 35;ISR_NOERR 36;ISR_NOERR 37;ISR_NOERR 38;ISR_NOERR 39
ISR_NOERR 40;ISR_NOERR 41;ISR_NOERR 42;ISR_NOERR 43;ISR_NOERR 44;ISR_NOERR 45;ISR_NOERR 46;ISR_NOERR 47

ISR_NOERR 128

.section .data
.global isr_stub_table
isr_stub_table:
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,128
    .quad isr_stub_\n
.endr

.section .text
isr_common:
    pushq %r15; pushq %r14; pushq %r13; pushq %r12
    pushq %r11; pushq %r10; pushq %r9; pushq %r8
    pushq %rbp; pushq %rdi; pushq %rsi; pushq %rdx
    pushq %rcx; pushq %rbx; pushq %rax
    movq %rsp, %rdi
    call interrupt_dispatch
    popq %rax; popq %rbx; popq %rcx; popq %rdx
    popq %rsi; popq %rdi; popq %rbp
    popq %r8; popq %r9; popq %r10; popq %r11
    popq %r12; popq %r13; popq %r14; popq %r15
    addq $16, %rsp
    iretq
