.global cpu_resume_user_mode
cpu_resume_user_mode:
    movq 0x00(%rdi), %r15
    movq 0x08(%rdi), %r14
    movq 0x10(%rdi), %r13
    movq 0x18(%rdi), %r12
    movq 0x20(%rdi), %r11
    movq 0x28(%rdi), %r10
    movq 0x30(%rdi), %r9
    movq 0x38(%rdi), %r8
    movq 0x40(%rdi), %rbp
    movq 0x48(%rdi), %rdi
    movq 0x50(%rdi), %rsi
    movq 0x58(%rdi), %rdx
    movq 0x60(%rdi), %rcx
    movq 0x68(%rdi), %rbx
    movq 0x70(%rdi), %rax
    movq 0x78(%rdi), %rsp
    pushq %rax
    movq 0x80(%rdi), %rax
    movq %rax, (%rsp)
    popq %rax
    iretq
