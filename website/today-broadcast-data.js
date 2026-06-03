export const todayBroadcast = {
  "generated_at": "2026-06-03T17:13:41.684996+08:00",
  "date_label": "May 31–Jun 03, 2026 (UTC+8)",
  "window_start_utc8": "2026-05-31",
  "window_end_utc8": "2026-06-03",
  "pool_note": "",
  "scoring": "area-keywords-title-abstract",
  "min_score": 4,
  "note": "Top arXiv papers from the last 7 days (UTC+8), ranked by area keyword score on title and abstract (same as Top picks by area).",
  "preview_limit": 3,
  "count": 3,
  "total_count": 8,
  "picks": [
    {
      "rank": 1,
      "title": "Agent libOS: A Library-OS-Inspired Runtime for Long-Running, Capability-Controlled LLM Agents",
      "authors": [
        "Yingqi Zhang"
      ],
      "score": 34,
      "abstract": "Large language model (LLM) agents are evolving from request-response assistants into long-running software actors: they maintain state across model calls, fork subtasks, wait for external events, request human authority, generate tools, and perform side effects that must be resumed and audited. This paper presents Agent libOS, a library-OS-inspired runtime substrate for LLM agents. Agent libOS runs above a conventional host operating system; it does not implement hardware drivers, kernel-mode isolation, or a POSIX-compatible operating system. Instead, it treats an agent as an AgentProcess: a schedulable execution subject with process identity, parent-child lineage, lifecycle state, a tool table derived from an AgentImage, typed Object Memory, explicit capabilities, human queues, checkpoints, events, and audit records. Its central design rule is tools are libc-like wrappers; runtime primitives are the authority boundary. Filesystem access, object access, sleeps, human approval, JIT tool registration, and external side effects are checked at primitive boundaries under explicit capabilities and policy. We describe the design, threat model, Python prototype, and safety-oriented evaluation. The current prototype implements async scheduling, namespace-local Object Memory, runtime-integrated human approval, one-shot permission grants, per-process working directories, shell and image-registration primitives, Deno/TypeScript JIT tools over a libOS syscall broker, filesystem/object bridge tools, an injectable Resource Provider Substrate, deterministic demos, real-model smoke scripts, and 123 regression tests at the time of writing. Rather than improving planner accuracy, Agent libOS demonstrates a runtime substrate in which long-running LLM agents can be scheduled, authorized, resumed, and audited without treating tool dispatch as the trust boundary.",
      "matched_tags": [
        "filesystem"
      ],
      "category_id": "fs-storage",
      "category_label": "File System and Storage",
      "published": "2026-06-02T16:53:24Z",
      "abs_url": "https://arxiv.org/abs/2606.03895v1",
      "pdf_url": "https://arxiv.org/pdf/2606.03895v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.03895v1"
    },
    {
      "rank": 2,
      "title": "Characterizing Metastable Faults and Failures",
      "authors": [
        "Ali Farahbakhsh",
        "Qingjie Lu",
        "Lorenzo Alvisi",
        "Andreas Haeberlen"
      ],
      "score": 16,
      "abstract": "Metastable failures are hard to detect, prevent, and mitigate. During a metastable failure, a system exhibits self-sustaining bad behavior even in the absence of adversarial conditions. Prior work focuses on symptoms and has portrayed metastable failures as instances of self-sustaining overload. This characterization leaves the underlying failure causes and dynamics unknown, and does not account for metastable failures that do not manifest as overload. We present the first causal characterization of metastable failures by identifying their origin in metastable faults, i.e., structural destabilizing cycles of interaction among systems components that, in isolation, are stabilizing. Metastable failures arise when scheduling decisions let these destabilizing interactions gain the upper hand over the individual components' stabilizing tendencies. We then derive a methodology to predict metastable failures, and to build metastable-fault-tolerant (MFT) systems. We apply our methodology to three case studies, showcasing the generality of our results.",
      "matched_tags": [
        "fault-tolerant"
      ],
      "category_id": "fault-tolerance",
      "category_label": "Fault Tolerance",
      "published": "2026-05-31T01:04:27Z",
      "abs_url": "https://arxiv.org/abs/2606.00942v2",
      "pdf_url": "https://arxiv.org/pdf/2606.00942v2",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00942v2"
    },
    {
      "rank": 3,
      "title": "Idleness is Relative: Exploiting Tool-Call Idle Windows for Offloading in Agentic Systems with MORI",
      "authors": [
        "Tian Xia",
        "Hanchen Li",
        "Zhifei Li",
        "Xiaokun Chen"
      ],
      "score": 47,
      "abstract": "Modern LLM serving systems increasingly host agentic workloads, whose sessions issue tens of model invocations interleaved with tool calls, accumulating KV cache that can be reused across steps. As requests' total KV cache size easily exceeds GPU HBM capacity, researchers offload them to CPU DRAM. However, tool-call durations span orders of magnitude, and the cost of transferring KV cache between tiers makes it impractical to re-place entries on every call. We observe that agentic programs exhibit a two-phase structure: busy phases of rapid short tool calls and idle phases dominated by long-running calls. Current eviction policies such as LRU fail to capture this property. A binary busy/idle label also falls short because the ratio of busy to idle programs may not match the hardware's GPU-to-CPU capacity ratio. When it does not, one tier sits underutilized while the other is oversubscribed, wasting memory or forcing unnecessary evictions. We present MORI, an agent serving system that solves the above problem. Our key insight is that idleness is a continuous, relative spectrum. MORI ranks all active programs by idleness, assigns the busiest to GPU HBM and the most idle to CPU DRAM, dynamically shifts the partition boundary to match hardware capacity, and enforces admission control at each memory tier. Evaluated on real coding agent workloads collected from Claude Code across four GPU and model pairs, MORI delivers 20--71% higher throughput and 18--43% lower TTFT than the best baseline with offloading.",
      "matched_tags": [
        "serving system",
        "throughput",
        "kv cache"
      ],
      "category_id": "llm-serving",
      "category_label": "LLM serving",
      "published": "2026-05-30T19:44:25Z",
      "abs_url": "https://arxiv.org/abs/2606.00866v1",
      "pdf_url": "https://arxiv.org/pdf/2606.00866v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00866v1"
    }
  ],
  "all_picks": [
    {
      "rank": 1,
      "title": "Agent libOS: A Library-OS-Inspired Runtime for Long-Running, Capability-Controlled LLM Agents",
      "authors": [
        "Yingqi Zhang"
      ],
      "score": 34,
      "abstract": "Large language model (LLM) agents are evolving from request-response assistants into long-running software actors: they maintain state across model calls, fork subtasks, wait for external events, request human authority, generate tools, and perform side effects that must be resumed and audited. This paper presents Agent libOS, a library-OS-inspired runtime substrate for LLM agents. Agent libOS runs above a conventional host operating system; it does not implement hardware drivers, kernel-mode isolation, or a POSIX-compatible operating system. Instead, it treats an agent as an AgentProcess: a schedulable execution subject with process identity, parent-child lineage, lifecycle state, a tool table derived from an AgentImage, typed Object Memory, explicit capabilities, human queues, checkpoints, events, and audit records. Its central design rule is tools are libc-like wrappers; runtime primitives are the authority boundary. Filesystem access, object access, sleeps, human approval, JIT tool registration, and external side effects are checked at primitive boundaries under explicit capabilities and policy. We describe the design, threat model, Python prototype, and safety-oriented evaluation. The current prototype implements async scheduling, namespace-local Object Memory, runtime-integrated human approval, one-shot permission grants, per-process working directories, shell and image-registration primitives, Deno/TypeScript JIT tools over a libOS syscall broker, filesystem/object bridge tools, an injectable Resource Provider Substrate, deterministic demos, real-model smoke scripts, and 123 regression tests at the time of writing. Rather than improving planner accuracy, Agent libOS demonstrates a runtime substrate in which long-running LLM agents can be scheduled, authorized, resumed, and audited without treating tool dispatch as the trust boundary.",
      "matched_tags": [
        "filesystem"
      ],
      "category_id": "fs-storage",
      "category_label": "File System and Storage",
      "published": "2026-06-02T16:53:24Z",
      "abs_url": "https://arxiv.org/abs/2606.03895v1",
      "pdf_url": "https://arxiv.org/pdf/2606.03895v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.03895v1"
    },
    {
      "rank": 2,
      "title": "Characterizing Metastable Faults and Failures",
      "authors": [
        "Ali Farahbakhsh",
        "Qingjie Lu",
        "Lorenzo Alvisi",
        "Andreas Haeberlen"
      ],
      "score": 16,
      "abstract": "Metastable failures are hard to detect, prevent, and mitigate. During a metastable failure, a system exhibits self-sustaining bad behavior even in the absence of adversarial conditions. Prior work focuses on symptoms and has portrayed metastable failures as instances of self-sustaining overload. This characterization leaves the underlying failure causes and dynamics unknown, and does not account for metastable failures that do not manifest as overload. We present the first causal characterization of metastable failures by identifying their origin in metastable faults, i.e., structural destabilizing cycles of interaction among systems components that, in isolation, are stabilizing. Metastable failures arise when scheduling decisions let these destabilizing interactions gain the upper hand over the individual components' stabilizing tendencies. We then derive a methodology to predict metastable failures, and to build metastable-fault-tolerant (MFT) systems. We apply our methodology to three case studies, showcasing the generality of our results.",
      "matched_tags": [
        "fault-tolerant"
      ],
      "category_id": "fault-tolerance",
      "category_label": "Fault Tolerance",
      "published": "2026-05-31T01:04:27Z",
      "abs_url": "https://arxiv.org/abs/2606.00942v2",
      "pdf_url": "https://arxiv.org/pdf/2606.00942v2",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00942v2"
    },
    {
      "rank": 3,
      "title": "Idleness is Relative: Exploiting Tool-Call Idle Windows for Offloading in Agentic Systems with MORI",
      "authors": [
        "Tian Xia",
        "Hanchen Li",
        "Zhifei Li",
        "Xiaokun Chen"
      ],
      "score": 47,
      "abstract": "Modern LLM serving systems increasingly host agentic workloads, whose sessions issue tens of model invocations interleaved with tool calls, accumulating KV cache that can be reused across steps. As requests' total KV cache size easily exceeds GPU HBM capacity, researchers offload them to CPU DRAM. However, tool-call durations span orders of magnitude, and the cost of transferring KV cache between tiers makes it impractical to re-place entries on every call. We observe that agentic programs exhibit a two-phase structure: busy phases of rapid short tool calls and idle phases dominated by long-running calls. Current eviction policies such as LRU fail to capture this property. A binary busy/idle label also falls short because the ratio of busy to idle programs may not match the hardware's GPU-to-CPU capacity ratio. When it does not, one tier sits underutilized while the other is oversubscribed, wasting memory or forcing unnecessary evictions. We present MORI, an agent serving system that solves the above problem. Our key insight is that idleness is a continuous, relative spectrum. MORI ranks all active programs by idleness, assigns the busiest to GPU HBM and the most idle to CPU DRAM, dynamically shifts the partition boundary to match hardware capacity, and enforces admission control at each memory tier. Evaluated on real coding agent workloads collected from Claude Code across four GPU and model pairs, MORI delivers 20--71% higher throughput and 18--43% lower TTFT than the best baseline with offloading.",
      "matched_tags": [
        "serving system",
        "throughput",
        "kv cache"
      ],
      "category_id": "llm-serving",
      "category_label": "LLM serving",
      "published": "2026-05-30T19:44:25Z",
      "abs_url": "https://arxiv.org/abs/2606.00866v1",
      "pdf_url": "https://arxiv.org/pdf/2606.00866v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00866v1"
    },
    {
      "rank": 4,
      "title": "Edge-Based QoS-Aware Adaptive Task Placement: A Closed-Loop Control in Multi-Robot Systems",
      "authors": [
        "Thien Tran",
        "Jonathan Kua",
        "Thuong Hoang",
        "Minh Tran"
      ],
      "score": 15,
      "abstract": "Multi-robot systems (MRS) increasingly offload compute-intensive perception tasks to edge nodes to meet strict time-sensitive Quality-of-Service (QoS) constraints. However, static task orchestration on a shared edge node can severely degrade QoS due to network latency, jitter, and edge-resource contention. We present a pilot edge-centric MRS testbed using Raspberry Pi nodes to evaluate a camera-to-manipulator pipeline under three modes: local execution, static offloading, and a QoS-aware Adaptive Task Placement (ATP) controller. ATP scores candidate placements using a multi-metric cost (normalized latency, CPU utilization, and switching overhead) over two-second control windows. The closed-loop visual servoing testbed is instrumented with sub-millisecond clock synchronization, network emulation, and detailed monitoring of multiple metrics across nodes to capture realistic jitter. Experimental results under compute-stress and network-fault scenarios show that static edge offloading reduces on-board CPU load but amplifies tail latency and deadline misses. In contrast, the QoS-aware ATP controller, by switching task placement based on measured latency and utilization thresholds, consistently lowers deadline violations and tail latency. Overall, the results position ATP as a practical edge-side control primitive for MRS and concrete design guidelines for Cloud-Edge Robotics deployments within the broader cloud-fog automation, while motivating QoS-aware multi-objective workload orchestration for industrial cyber-physical systems.",
      "matched_tags": [
        "latency"
      ],
      "category_id": "llm-serving",
      "category_label": "LLM serving",
      "published": "2026-05-30T05:54:44Z",
      "abs_url": "https://arxiv.org/abs/2606.00552v1",
      "pdf_url": "https://arxiv.org/pdf/2606.00552v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00552v1"
    },
    {
      "rank": 5,
      "title": "Beyond Edge Coverage: Per-Task Data-Flow Extraction at Kernel Function Boundaries via LLVM",
      "authors": [
        "Yunseong Kim"
      ],
      "score": 14,
      "abstract": "Coverage-guided kernel fuzzers such as syzkaller rely on edge coverage (trace-pc) as their sole feedback signal. This context-blind approach cannot distinguish execution paths that differ only in argument values. for example, two invocations of copy_from_user() with different size parameters hit identical basic blocks yet have vastly different security implications. We present BOUNDARY FLOW, an LLVM-based instrumentation framework that extends Linux KCOV with data-flow extraction of function arguments and return values. A compiler pass (-fsanitize-coverage=dataflow-args, dataflow-ret) emits lightweight callbacks capturing a structured tuple <PC, arg_idx, arg_size, ptr, offsets[]> at function entry and <PC, ret_size, ptr, offsets[]> at return. Composite types are automatically decomposed via DWARF DICompositeType metadata with zero source annotation. A separate kernel device(/sys/kernel/debug/kcov_dataflow) provides lock-free per-task ring buffers with no inter ference to existing KCOV or syzkaller infrastructure. We demonstrate dual utility: fuzzers gain state-aware feedback for mutation guidance into value-dependent state transitions, and security analysts obtain deterministic argument records for root-cause analysis without printk or kprobe overhead. A post-compilation pipeline (rustc, opt, llc) enables Rust kernel module instrumentation without modifying rustc, the only runtime method for capturing Rust function arguments given that drgn/vmcore fails under-O2 DWARF elision. Evaluated on five vulnerability classes (OOB, UAF, double-free, 10 deep chain propagation, Rust FFI, Rust for Linux Modules) with <3% overhead on instrumented paths.",
      "matched_tags": [
        "vulnerability",
        "security"
      ],
      "category_id": "system-security",
      "category_label": "System Security",
      "published": "2026-05-30T00:42:59Z",
      "abs_url": "https://arxiv.org/abs/2606.00455v1",
      "pdf_url": "https://arxiv.org/pdf/2606.00455v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2606.00455v1"
    },
    {
      "rank": 6,
      "title": "RTP-LLM: High-Performance Alibaba LLM Inference Engine",
      "authors": [
        "Boyu Tan",
        "Jiarui Guo",
        "Zongwei Lv",
        "Hanbo Sun"
      ],
      "score": 67,
      "abstract": "Large Language Models (LLMs) have revolutionized AI applications, but deploying them at scale presents significant challenges. We present RTP-LLM, a high-performance inference engine for industrial-scale LLM deployment, successfully deployed across Alibaba Group serving over 100 million users. RTP-LLM addresses fundamental bottlenecks through integrated design. It optimizes model loading via file-order-driven I/O and parallel I/O-communication overlapping. The Prefill-Decode Disaggregation architecture decouples compute-intensive prefill from memory-bound decode phases, combined with hierarchical multi-tiered KV cache management enabling efficient cache reuse. In addition, RTP-LLM incorporates modular speculative decoding supporting multiple algorithms, adaptive KV cache quantization, and decoupled multimodal processing, with support for multi-level parallelism. Comprehensive evaluations across diverse model architectures (8B-235B parameters) have been conducted, where both controlled benchmarks and real production workloads are used. The results demonstrate RTP-LLM's superior performance against vLLM and SGLang: 4.7x-6.3x model loading speedup, 35-37% TTFT P95 latency reduction with 215% cache reuse improvement in production traffic scheduling, 1.12x-2.48x and 1.86x-2.52x throughput improvements in speculative decoding and multimodal inference, respectively, and 35-40% batch latency reduction with 1.9x-3.0x TTFT improvement in quantized inference. RTP-LLM's production-proven architecture and open-source availability make it a comprehensive solution for industrial LLM deployment.",
      "matched_tags": [
        "speculative decoding",
        "llm inference",
        "throughput",
        "kv cache",
        "latency",
        "vllm"
      ],
      "category_id": "llm-serving",
      "category_label": "LLM serving",
      "published": "2026-05-28T09:07:06Z",
      "abs_url": "https://arxiv.org/abs/2605.29639v1",
      "pdf_url": "https://arxiv.org/pdf/2605.29639v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2605.29639v1"
    },
    {
      "rank": 7,
      "title": "IORM: Hierarchical I/O Governance for Thousands of Consolidated Databases on Oracle Exadata",
      "authors": [
        "Rajarshi Chowdhury",
        "Akshay Shah",
        "Zakaria Alrmaih",
        "Chenhao Guo"
      ],
      "score": 14,
      "abstract": "Oracle Exadata consolidates thousands of tenant databases onto shared storage infrastructure deployed at hundreds of customer sites worldwide. Oracle Multitenant architecture enables this extreme density, with thousands of tenant databases sharing a single Exadata storage system -- but this creates a multi-level resource hierarchy (container databases, tenant databases, and workloads within tenants) that commodity block-layer schedulers cannot govern, as they lack visibility into database semantics and tenant boundaries. This paper presents the I/O Resource Manager (IORM), a storage-side scheduler built on three mechanisms: I/O Tagging, which propagates semantic context from the database kernel to the storage scheduler; Hierarchical Resource Profiles, which express compositional allocation policies across consolidation tiers using shares and limits; and Unified Storage Governance, which applies these policies consistently across all tiers of the storage hierarchy -- persistent memory, flash, and hard disk -- including cache placement decisions. IORM enables successful cloud deployments where thousands of tenants coexist on shared storage: production OLTP workloads run alongside concurrent analytical workloads from the same or different databases without noisy-neighbor interference. Evaluation on production Exadata systems demonstrates that IORM dramatically improves latency consistency, virtually eliminating tail latency outliers and delivering several-fold improvements in average read latency under mixed workloads. Hierarchical limits compose correctly across all three levels, and proportional share allocation tracks configured ratios closely even under highly skewed demand.",
      "matched_tags": [
        "storage system"
      ],
      "category_id": "fs-storage",
      "category_label": "File System and Storage",
      "published": "2026-05-27T19:02:45Z",
      "abs_url": "https://arxiv.org/abs/2605.29006v1",
      "pdf_url": "https://arxiv.org/pdf/2605.29006v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2605.29006v1"
    },
    {
      "rank": 8,
      "title": "A Secure, Manifest-Based Framework for Delegated Privilege Promotion",
      "authors": [
        "Rajarshi Chowdhury",
        "Akshay Shah"
      ],
      "score": 4,
      "abstract": "Large-scale enterprise software systems commonly run as unprivileged service accounts to enforce least privilege, yet still depend on a small set of privileged components -- such as executables with elevated ownership, permissions, or capabilities -- for narrowly scoped operations. This creates a persistent security and operational conflict during maintenance. Automated patching tools running without elevated privileges cannot safely update privileged components without either executing the entire patch with full administrative rights or requiring manual administrator intervention. We present a secure, manifest-based infrastructure for delegated promotion of privileged software components, deployed in production as part of a large-scale enterprise database system serving both cloud and on-premises installations. The design centers on a minimal privileged mediator that validates cryptographically protected metadata and allows an unprivileged process to promote only vendor-approved files. The system explicitly mitigates Time-of-Check-to-Time-of-Use (TOCTOU) attacks using file-descriptor-bound validation and promotion, supports offline key rotation and revocation, and enables zero-downtime self-update via atomic replacement.",
      "matched_tags": [
        "security"
      ],
      "category_id": "system-security",
      "category_label": "System Security",
      "published": "2026-05-27T18:48:47Z",
      "abs_url": "https://arxiv.org/abs/2605.28991v1",
      "pdf_url": "https://arxiv.org/pdf/2605.28991v1",
      "source_feed": "cs.OS",
      "arxiv_id": "2605.28991v1"
    }
  ]
};
