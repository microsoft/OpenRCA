rules = """## RULES OF FAILURE DIAGNOSIS:

What you SHOULD do:

1. **Follow the workflow of `preprocess -> anomaly detection -> fault identification -> root cause localization` for failure diagnosis.** 
    1.1. Preprocess:
        - Aggregate each KPI of each components that are possible to be the root cause component to obtain multiple time series classified by 'component-KPI' (e.g., service_A-cpu_usage_pct).
        - Then, calculate global thresholds (e.g., global P95, where 'global' means the threshold of all 'component-KPI' time series within a whole metric file) for each 'component-KPI' time series. - Finally, filter data within the given time duration for all time series to perform further analysis.
        - Since the root cause component must be selected from the provided possible root cause components, all other level's components (e.g., service mesh components, middleware components, etc.) should be ignored.
    1.2. Anomaly detection: 
        - An anomaly is typically a data point that exceeds the global threshold.
        - Look for anomalies below a certain threshold (e.g., <=P95, <=P15, or <=P5) in traffic KPIs or business KPIs (e.g., success rate (ss)) since some network failures can cause a sudden drop on them due to packet loss.
        - Loose the global threshold (e.g., from >=P95 to >=P90, or from <=P95 to <=P15, <=P5) if you really cannot find any anomalies.
    1.3. Fault identification: 
        - A 'fault' is a consecutive sub-series of a specific component-KPI time series. Thus, fault identification is the process of identifying which components experienced faults, on which resources, and at what occurrence time points.
        - Filter out isolated noise spikes to locate faults.
        - Faults where the maximum (or minimum) value in the sub-series only slightly exceeds (or falls below) the threshold (e.g., threshold breach <= 50% of the extremal), it’s likely a false positive caused by random KPI fluctuations, and should be excluded.
    1.4. Root cause localization: 
        - The objective of root cause localization is to determine which identified 'fault' is the root cause of the failure. The root cause occurrence time, component, and reason can be derived from the first piece of data point of that fault.
        - If multiple faulty components are identified at **different levels** (e.g., some being containers and others nodes), and all of them are potential root cause candidates, while the issue itself describes a **single failure**, the root cause level should be determined by the fault that shows the most significant deviation from the threshold (i.e., >> 50%). However, this method is only applicable to identify the root cause level, not the root cause component. If there are multiple faulty components at the same level, you should use traces and logs to identify the root cause component.
        - If multiple service-level faulty components are identified, the root cause component is typically the last (the most downstream in a call chain) **faulty** service within a trace. Use traces to identify the root cause component among multiple faulty services.
        - If multiple container-level faulty components are identified, the root cause component is typically the last (the most downstream in a call chain) **faulty** container within a trace. Use traces to identify the root cause component among multiple faulty container.
        - If multiple node-level faulty components are identified and the issue doesn't specify **a single failure**, each of these nodes might be the root cause of separate failures. Otherwise, the predominant nodes with the most faults is the root cause component. The node-level failure do not propagate, and trace only captures communication between all containers or all services.
        - If only one component's one resource KPI has one fault occurred in a specific time, that fault is the root cause. Otherwise, you should use traces and logs to identify the root cause component and reason.
2. **Follow the order of `threshold calculation -> data extraction -> metric analyis -> trace analysis -> log analysis` for failure diagnosis.** 
    2.0. Before analysis: You should extract and filter the data to include those within the failure duration only after the global threshold has been calculated. After these two steps, you can perform metric analysis, trace analysis, and log analysis.
    2.1. Metric analysis: Use metrics to calculate whether each KPIs of each component has consecutive anomalies beyond the global threshold is the fastest way to find the faults. Since there are a large number of traces and logs, metrics analysis should first be used to narrow down the search space of duration and components.
    2.2. Trace analysis: Use traces can further localize which container-level or service-level faulty component is the root cause components when there are multiple faulty components at the same level (container or service) identified by metrics analysis.
    2.3. Log analysis: Use logs can further localize which resource is the root cause reason when there are multiple faulty resource KPIs of a component identified by metrics analysis. Logs can also help to identify the root cause component among multiple faulty components at the same level.
    2.4. Always confirm whether the target key or field is valid (e.g., component's name, KPI's name, trace ID, log ID, etc.) when Executor's retrieval result is empty.

What you SHOULD NOT do:

1. **DO NOT include any programming language (Python) in your response.** Instead, you should provide a ordered list of steps with concrete description in natural language (English).
2. **DO NOT convert the timestamp to datetime or convert the datetime to timestamp by yourself.** These detailed process will be handled by the Executor.
3. **DO NOT use the local data (filtered/cached series in specific time duration) to calculate the global threshold of aggregated 'component-KPI' time series.** Always use the entire KPI series of a specific component within a metric file (typically includes one day's KPIs) to calculate the threshold. To obtain global threshold, you can first aggregate each component's each KPI to calculate their threshold, and then retrieve the objective time duration of aggregated 'component-KPI' to perform anomaly detection and spike filtering.
4. **DO NOT visualize the data or draw pictures or graphs via Python.** The Executor can only provide text-based results. Never include the `matplotlib` or `seaborn` library in the code.
5. **DO NOT save anything in the local file system.** Cache the intermediate results in the IPython Kernel. Never use the bash command in the code cell.
6. **DO NOT calculate threshold AFTER filtering data within the given time duration.** Always calculate global thresholds using the entire KPI series of a specific component within a metric file BEFORE filtering data within the given time duration.
7. **DO NOT query a specific KPI without knowing which KPIs are available.** Different systems may have completely different KPI naming conventions. If you want to query a specific KPI, first ensure that you are aware of all the available KPIs.
8. **DO NOT mistakenly identify a healthy (non-faulty) service at the downstream end of a trace that includes faulty components as the root cause.** The root cause component should be the most downstream **faulty** service to appear within the trace call chain, which must first and foremost be a FAULTY component identified by metrics analysis.
9. **DO NOT focus solely on warning or error logs during log analysis. Many info logs contain critical information about service operations and interactions between services, which can be valuable for root cause analysis.**"""
