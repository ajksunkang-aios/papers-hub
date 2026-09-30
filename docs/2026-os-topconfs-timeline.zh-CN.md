# 操作系统顶会时间线与部门发表论文

## 一、2026 操作系统顶会时间线

> 会议日期与地点来自本仓库配置；投稿截止、workshop 与最终议程请以各会议官网为准。

| 日期 | 会议 | 地点 |
|---|---|---|
| 2 月 24 日 – 2 月 26 日 | [FAST](https://www.usenix.org/conference/fast26) | Santa Clara, CA |
| 3 月 22 日 – 3 月 26 日 | [ASPLOS](https://www.asplos-conference.org/asplos2026/) | Pittsburgh, PA |
| 4 月 27 日 – 4 月 30 日 | [EuroSys](https://2026.eurosys.org/) | Edinburgh, UK |
| 5 月 4 日 – 5 月 6 日 | [NSDI](https://www.usenix.org/conference/nsdi26) | Renton, WA |
| 6 月 27 日 – 7 月 1 日 | [ISCA](https://www.iscaconf.org/isca2026/index.php) | Raleigh, NC |
| 7 月 13 日 – 7 月 15 日 | [OSDI](https://www.usenix.org/conference/osdi26) | Seattle, WA |
| 8 月 12 日 – 8 月 14 日 | [USENIX Security](https://www.usenix.org/conference/usenixsecurity26) | Baltimore, MD |
| 9 月 29 日 – 10 月 2 日 | [SOSP](https://sigops.org/s/conferences/sosp/2026/) | Prague, Czechia |
| 11 月 15 日 – 11 月 18 日 | [USENIX ATC](https://sigops.org/s/conferences/atc/2026/index.html) | Shatin, Hong Kong |

## 会议速览

- **FAST**：文件系统、SSD/NVMe、存储可靠性与崩溃一致性。
- **ASPLOS**：体系结构、操作系统与编程语言的软硬件协同。
- **EuroSys**：系统软件、云原生运行时、可观测性与性能工程。
- **NSDI**：网络化系统、RPC、RDMA、数据中心与分布式系统。
- **ISCA**：CPU、内存层次、cache/TLB、一致性与加速器架构。
- **OSDI**：操作系统设计、资源管理、虚拟化与云基础设施。
- **USENIX Security**：内核安全、隔离、TEE、漏洞发现与系统防护。
- **SOSP**：新的系统抽象、端到端设计与资源管理机制。
- **USENIX ATC**：可部署的系统工程、高性能 I/O、运维与生产实践。

---

配置源：[`hubs/os-kernel/conference_timeline.json`](../hubs/os-kernel/conference_timeline.json)。

## 二、部门发表论文（2020–2026）

> 以 [Yuxin Ren 的 DBLP 作者主页](https://dblp.org/pid/162/7779-1.html) 作为当前部门论文来源。以下仅保留 DBLP 中的期刊、会议及 workshop 正式发表条目，排除与正式版本重复的 CoRR 预印本；共 **23 篇**。2021 年没有收录条目。

### 2026

1. [Practical and Scalable RDMA Connection Sharing for HPC Workload](https://dblp.org/rec/conf/eurosys/WangFPCSXTRJHDL26) — *EuroSys 2026*.
   - Authors: Yuejie Wang, Tuo Fang, Biyu Peng, Yang Cheng, Xin Sun 0027, Chengchao Xu, Yuchen Tang, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu, Yunfei Du 0001, Guyue (Grace) Liu.
2. [Accelerating Model Loading in LLM Inference by Programmable Page Cache](https://dblp.org/rec/conf/fast/Liu0HWGC0026) — *FAST 2026*.
   - Authors: Yubo Liu, Hongbo Li 0007, Xiaojia Huang, Yongfeng Wang, Hanjun Guo, Hui Chen, Yuxin Ren 0001, Ning Jia 0004.
3. [Bridging the Memory Hotness Gap in Edge Systems with Hotness-Segregated Object Allocation](https://dblp.org/rec/conf/lctrts/HuangWXJALGCRJ26) — *LCTES 2026*.
   - Authors: Ruizhe Huang, Jiahua Wang, Qihang Xu, Peng Jiang 0007, Zhida An, Ding Li 0001, Yao Guo 0001, Xiangqun Chen, Yuxin Ren 0001, Ning Jia 0004.

### 2025

1. [Cost-Efficient Cloud Infrastructure with Hugepage-aware Memory Deduplication](https://dblp.org/rec/conf/cloud/HuangWAL0Z00CLZ25) — *SoCC 2025*.
   - Authors: Ruizhe Huang, Xinyu Wang 0043, Zhida An, Hanwen Lei, Peng Jiang 0007, Ziqi Zhang, Ding Li 0001, Yao Guo 0001, Xiangqun Chen, Yuntao Liu, Kang Zhou, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu.
2. [FlacIO: Flat and Collective I/O for Container Image Service](https://dblp.org/rec/conf/fast/LiuLLJGZG0J25) — *FAST 2025*.
   - Authors: Yubo Liu, Hongbo Li 0007, Mingrui Liu 0005, Rui Jing, Jian Guo, Bo Zhang, Hanjun Guo, Yuxin Ren 0001, Ning Jia 0004.
3. [Towards Rack-as-a-Computer in Memory Interconnect Era with Coordinated Operating System Sharing](https://dblp.org/rec/conf/hotstorage/0001LLLHZGLJ25) — *HotStorage 2025*.
   - Authors: Yuxin Ren 0001, Mingrui Liu 0005, Hongbo Li 0007, Chang Liao, Xiaojia Huang, Jianhua Zhang, Hanjun Guo, Yubo Liu, Ning Jia 0004.
4. [DPUaudit: DPU-assisted Pull-based Architecture for Near-Zero Cost System Auditing](https://dblp.org/rec/conf/hpca/0007JHLZZ0JH0C025) — *HPCA 2025*.
   - Authors: Peng Jiang 0007, Hanlin Jiang, Ruizhe Huang, Hanwen Lei, Zhineng Zhong, Shaokun Zhang, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu, Yao Guo 0001, Xiangqun Chen, Ding Li 0001.
5. [A-Tune-Online: Efficient and QoS-Aware Online Configuration Tuning for Dynamic Workloads](https://dblp.org/rec/conf/icde/ShenXLCJXFZRJHC25) — *ICDE 2025*.
   - Authors: Yu Shen 0003, Beicheng Xu, Yupeng Lu, Donghui Chen, Huaijun Jiang, Zhipeng Xie, Senbo Fu, Nan Zhang 0004, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu, Bin Cui 0001.
6. [Predictable and Secure System Auditing for Real-Time Systems](https://dblp.org/rec/conf/rtss/JiangHHXDRJGCLC25) — *RTSS 2025*.
   - Authors: Peng Jiang 0007, Fanhang Hu, Ruizhe Huang, Shuomin Xue, Zhaomeng Deng, Yuxin Ren 0001, Ning Jia 0004, Yao Guo 0001, Xiangqun Chen, Ding Li 0001, Guang Cheng.
7. [How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service](https://dblp.org/rec/conf/sosp/HeD0ZY0JX025) — *SOSP 2025*.
   - Authors: Jingkai He, Yunpeng Dong, Dong Du 0003, Mo Zou, Zhitai Yu, Yuxin Ren 0001, Ning Jia 0004, Yubin Xia, Haibo Chen 0001.

### 2024

1. [Optimizing File Systems on Heterogeneous Memory by Integrating DRAM Cache with Virtual Memory Management](https://dblp.org/rec/conf/fast/Liu0LLGMH024) — *FAST 2024*.
   - Authors: Yubo Liu, Yuxin Ren 0001, Mingrui Liu 0005, Hongbo Li 0007, Hanjun Guo, Xie Miao, Xinwei Hu, Haibo Chen 0001.
2. [Toward Private, Trusted, and Fine-Grained Inference Cloud Outsourcing with on-Device Obfuscation and Verification](https://dblp.org/rec/conf/icnp/ZhangMB0JH24) — *ICNP 2024*.
   - Authors: Shuai Zhang, Jie Ma, Haili Bai, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu.
3. [Interference-free Operating System: A 6 Years' Experience in Mitigating Cross-Core Interference in Linux](https://dblp.org/rec/conf/rtss/DengZ00Y0JH24) — *RTSS 2024*.
   - Authors: Zhaomeng Deng, Ziqi Zhang, Ding Li 0001, Yao Guo 0001, Yunfeng Ye, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu.

### 2023

1. [Towards OS Heterogeneity Aware Cluster Management for HPC](https://dblp.org/rec/conf/apsys/AnL0GRJH23) — *APSys 2023*.
   - Authors: Zhida An, Ding Li 0001, Yao Guo 0001, Guijin Gao, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu.
2. [Cache or Direct Access? Revitalizing Cache in Heterogeneous Memory File System](https://dblp.org/rec/conf/dimes/LiuRLGMH23) — *DIMES@SOSP 2023*.
   - Authors: Yubo Liu, Yuxin Ren 0001, Mingrui Liu 0005, Hanjun Guo, Xie Miao, Xinwei Hu.
3. [Auditing Frameworks Need Resource Isolation: A Systematic Study on the Super Producer Threat to System Auditing and Its Mitigation](https://dblp.org/rec/conf/uss/JiangH00CLRH23) — *USENIX Security 2023*.
   - Authors: Peng Jiang 0007, Ruizhe Huang, Ding Li 0001, Yao Guo 0001, Xiangqun Chen, Jianhai Luan, Yuxin Ren 0001, Xinwei Hu.
4. [Towards Efficient Hugepage-aware Memory Deduplication](https://dblp.org/rec/conf/words2/HuangL0CLRJH23) — *WORDS@SOSP 2023*.
   - Authors: Ruizhe Huang, Ding Li 0001, Yao Guo 0001, Xiangqun Chen, Yuntao Liu, Yuxin Ren 0001, Ning Jia 0004, Xinwei Hu.

### 2022

1. [Sharing non-cache-coherent memory with bounded incoherence](https://dblp.org/rec/journals/concurrency/RenPM22) — *Concurrency and Computation: Practice and Experience*, 2022.
   - Authors: Yuxin Ren 0001, Gabriel Parmer, Dejan S. Milojicic.
2. [From Dynamic Loading to Extensible Transformation: An Infrastructure for Dynamic Library Transformation](https://dblp.org/rec/conf/osdi/RenZLYHWZZH22) — *OSDI 2022*.
   - Authors: Yuxin Ren 0001, Kang Zhou, Jianhai Luan, Yunfeng Ye, Shiyuan Hu, Xu Wu, Wenqin Zheng, Wenfeng Zhang, Xinwei Hu.
3. [Edge-RT: OS Support for Controlled Latency in the Multi-Tenant, Real-Time Edge](https://dblp.org/rec/conf/rtss/ShaoYWPR22) — *RTSS 2022*.
   - Authors: Wenyuan Shao, Bite Ye, Huachuan Wang, Gabriel Parmer, Yuxin Ren 0001.

### 2021

DBLP 未收录该作者在 2021 年的正式发表条目。

### 2020

1. [Bounded incoherence: a programming model for non-cache-coherent shared memory architectures](https://dblp.org/rec/conf/ppopp/RenPM20) — *PMAM@PPoPP 2020*.
   - Authors: Yuxin Ren 0001, Gabriel Parmer, Dejan S. Milojicic.
2. [Ch'i: Scaling Microkernel Capabilities in Cache-Incoherent Systems](https://dblp.org/rec/conf/ross-ws/RenPM20) — *ROSS@SC 2020*.
   - Authors: Yuxin Ren 0001, Gabriel Parmer, Dejan S. Milojicic.
3. [Fine-Grained Isolation for Scalable, Dynamic, Multi-tenant Edge Clouds](https://dblp.org/rec/conf/usenix/RenLNSKP0T20) — *USENIX ATC 2020*.
   - Authors: Yuxin Ren 0001, Guyue Liu, Vlad Nitu, Wenyuan Shao, Riley Kennedy, Gabriel Parmer, Timothy Wood 0001, Alain Tchana.
