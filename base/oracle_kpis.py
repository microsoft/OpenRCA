kpi_Telecom = {
    "db": ["Proc_Used_Pct",
           "Sess_Connect",
           "Proc_User_Used_Pct",
           "On_Off_State",
           "tnsping_result_time",
           ],
    "cpu": ["container_cpu_used",
            ],
    "mem": ["Memory_used_pct",
            ],
    "io": ["Disk_io_util"
            ],
    "net": ["Sent_queue",
            "Received_queue",
            ]
    
}

kpi_Telecom_len = sum(len(v) for v in kpi_Telecom.values())


kpi_Bank = {
    "jvm": ["JVM-Operating System_7779_JVM_JVM_CPULoad",
            "JVM-Operating System_7778_JVM_JVM_CPULoad",
            "JVM-Memory_7778_JVM_Memory_NoHeapMemoryUsed",
            "JVM-Memory_7779_JVM_Memory_NoHeapMemoryUsed",
            "JVM-Memory_7779_JVM_Memory_HeapMemoryUsage",
            "JVM-Memory_7778_JVM_Memory_HeapMemoryUsage",
            "JVM-Memory_7778_JVM_Memory_HeapMemoryUsed",
            "JVM-Memory_7779_JVM_Memory_HeapMemoryUsed",
            ],
    
    "cpu": ["OSLinux-CPU_CPU_CPUCpuUtil",
            "OSLinux-CPU_CPU-0_SingleCpuUtil",
            ],
    
    "mem": ["OSLinux-OSLinux_MEMORY_MEMORY_MEMUsedMemPerc",
            "OSLinux-OSLinux_MEMORY_MEMORY_NoCacheMemPerc",
            "OSLinux-OSLinux_MEMORY_MEMORY_MEMFreeMem",
            ],
    
    "io": ["OSLinux-OSLinux_LOCALDISK_LOCALDISK-sda_DSKReadWrite",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sdb_DSKRead",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sdb_DSKReadWrite",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sdb_DSKRTps",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sda_DSKRTps",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sda_DSKRead",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sda_DSKBps",
           "OSLinux-OSLinux_LOCALDISK_LOCALDISK-sda_DSKPercentBusy",
           ],
    
    "net": ["OSLinux-OSLinux_NETWORK_NETWORK_TCP-FIN-WAIT",
            "OSLinux-OSLinux_NETWORK_ens160_NETBandwidthUtil",
            "OSLinux-OSLinux_NETWORK_NETWORK_TotalTcpConnNum",
            "OSLinux-OSLinux_NETWORK_ens160_NETPacketsOut",
            "OSLinux-OSLinux_NETWORK_ens160_NETPacketsIn",
            "OSLinux-OSLinux_NETWORK_ens160_NETKBTotalPerSec",
            "OSLinux-OSLinux_NETWORK_NETWORK_TCP-CLOSE-WAIT"
            ]
}


kpi_Bank_len = sum([len(v) for v in kpi_Bank.values()])


kpi_Market = {
    "process": ["container_threads",
                ],
    
    "cpu": ["container_cpu_usage_seconds",
            "system.cpu.pct_usage",
            ],
    
    "mem": ["system.mem.used",
            "container_memory_usage_MB",
            ],
    
    "io": ["container_fs_reads./dev/vda",
           "container_fs_writes./dev/vda",
           "system.io.r_s",
           "system.io.w_s",
           "container_fs_writes./dev/vda1",
           "system.disk.used",
           "system.disk.pct_usage",
           ],
    
    "net": ["container_network_receive_packets.eth0",
            "container_network_receive_MB.eth0",
            "recommendationservice-grpc",
            "frontend-http",
            "cartservice-grpc",
            "checkoutservice-grpc",
            "productcatalogservice-grpc",
            "emailservice-grpc",
            "adservice-grpc",
            ],
}

kpi_Market_len = sum([len(v) for v in kpi_Market.values()])