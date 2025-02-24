import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
import pandas as pd
import argparse
from datetime import datetime
from loguru import logger
from copy import deepcopy

from rca.baseline.direct_lm import DirectLM
from rca.baseline.cot_lm import CoTLM
from main.evaluate import evaluate
from time import time
from rca.api_router import configs

import random

import tiktoken
tokenizer = tiktoken.encoding_for_model("gpt-4o")

def cache_df_dict(dataset_name:str):

    df_dict = dict()
    
    if dataset_name == "Telecom":
        from rca.baseline.oracle_kpis import kpi_Telecom_len
        selected_kpi_len = kpi_Telecom_len
        
        example_df_dict = {
            "metric": [],
            "trace": [],
        }
        dataset_path = "Telecom"
        
        import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp
        cand = bp.cand
        
    elif dataset_name == "Bank":
        from rca.baseline.oracle_kpis import kpi_Bank_len
        selected_kpi_len = kpi_Bank_len
        
        example_df_dict = {
            "log": [],
            "metric": [],
            "trace": [],
        }
        dataset_path = "Bank"

        import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp
        cand = bp.cand
        
    elif dataset_name == "Market/cloudbed-1":
        from rca.baseline.oracle_kpis import kpi_Market_len
        selected_kpi_len = kpi_Market_len
        
        example_df_dict = {
            "log": [],
            "metric": [],
            "trace": [],
        }
        dataset_path = "Market/cloudbed-1"

        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp
        cand = bp.cand
        
    elif dataset_name == "Market/cloudbed-2":
        from rca.baseline.oracle_kpis import kpi_Market_len
        selected_kpi_len = kpi_Market_len
        
        example_df_dict = {
            "log": [],
            "metric": [],
            "trace": [],
        }
        dataset_path = "Market/cloudbed-2"

        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp
        cand = bp.cand
        
    for day_time in os.listdir(f"dataset/{dataset_path}/telemetry/"):
        if day_time == '.DS_Store':
                continue
        if day_time not in df_dict:
            df_dict[day_time] = deepcopy(example_df_dict)
            
        for data_type in os.listdir(f"dataset/{dataset_path}/telemetry/{day_time}"):
            if data_type == '.DS_Store':
                continue
            for fname in os.listdir(f"dataset/{dataset_path}/telemetry/{day_time}/{data_type}"):
                t0 = time()
                cur_df = pd.read_csv(f"dataset/{dataset_path}/telemetry/{day_time}/{data_type}/{fname}")
                t1 = time()
                logger.debug(f"{round(t1-t0,1)} seconds for reading {fname}")
                
                #preprocess
                cur_df = cur_df.reset_index()
                if "timestamp" in cur_df.columns:
                    col = "timestamp"
                elif "startTime" in cur_df.columns:
                    col = "startTime"
                else:
                    logger.error("There is no 'startTime' or 'timestamp' indicating the timestamp of the data entries")
                    raise IndexError
                cur_df[col] = cur_df[col].apply(lambda x: int(x // 1000) if len(str(x)) == 13 else x)
                t2 = time()
                logger.debug(f"{round(t2-t1, 1)} seconds for prerpocessing DataFrame")
                if cur_df.empty:
                    logger.warning(f"{fname} is empty")
                else:
                    df_dict[day_time][data_type].append((fname, cur_df))
                
    return df_dict, selected_kpi_len, cand


def extract_period_data(df_list:list, data_type:str, target_timestamp:int, sample_interval=60, selected_kpi=None, selected_kpi_len=None) -> list:

    logger.debug(f"Extracting {data_type} data ...")
    
    extracted_data = ""
    for fname, df_file in df_list:

        if data_type == "metric" and len(selected_kpi) >= selected_kpi_len:
            logger.info(f"Selected KPI number ({len(selected_kpi)}) have reached the limit: {selected_kpi_len}")
            break
        
        if "timestamp" in df_file.columns:
            col = "timestamp"
        elif "startTime" in df_file.columns:
            col = "startTime"
        else:
            logger.error("There is no 'startTime' or 'timestamp' indicating the timestamp of the data entries")
            raise IndexError
                
        t1 = time()
        start_timestamp = target_timestamp - target_timestamp % 1800
        end_timestamp = start_timestamp + 1800
        filtered_df = df_file[(df_file[col] >= start_timestamp) & (df_file[col] <= end_timestamp)]
        filtered_df = filtered_df.drop(columns=["index"])
        
        t2 = time()
        logger.debug(f"{round(t2-t1,1)} seconds for filtering 30 min data")

        if data_type == "log":
            filtered_df = filtered_df.drop(columns=["log_id"])
            filtered_df = filtered_df.drop(columns=["cmdb_id"])
            filtered_df = filtered_df.drop(columns=["log_name"])
            schema = filtered_df.columns
            extracted_data = extracted_data + f'\n\n#### {fname}'
            extracted_data = extracted_data + f' Schema: '  + ','.join(schema) + '\n'
            resampled_df = filtered_df.groupby(filtered_df[col] // (sample_interval/5)).first()
            if resampled_df.empty:
                extracted_data = extracted_data + "DATA NOT AVAILABLE\n"
            else:
                data = resampled_df.astype(str).agg(','.join, axis=1)
                extracted_data = extracted_data + '\n'.join(data) + '\n'
        elif data_type == "trace":
            opt_traceid_field_name = ["traceId", "trace_id"]
            traceid_field_name = None
            for opt_name in opt_traceid_field_name:
                if opt_name in df_file.columns:
                    traceid_field_name = opt_name
            if traceid_field_name==None:
                logger.error("There is no 'traceId' or 'trace_id' indicating the trace_id of the data entries")
                raise IndexError
            opt_spanid_field_name = ["id", "span_id"]
            spanid_field_name = None
            for opt_name in opt_spanid_field_name:
                if opt_name in df_file.columns:
                    spanid_field_name = opt_name
            if spanid_field_name==None:
                logger.error("There is no 'id' or 'span_id' indicating the span_id of the data entries")
                raise IndexError
            opt_parent_field_name = ["pid", "parent_id", "parent_span"]
            parent_field_name = None
            for opt_name in opt_parent_field_name:
                if opt_name in df_file.columns:
                    parent_field_name = opt_name
            if parent_field_name==None:
                logger.error("There is no 'pid' or 'parent_id' indicating the parent_id of the data entries")
                raise IndexError
            opt_duration_field_name = ["elapsedTime", "duration"]
            duration_field_name = None
            for opt_name in opt_duration_field_name:
                if opt_name in df_file.columns:
                    duration_field_name = opt_name
            
            filtered_df = filtered_df[[col, traceid_field_name, spanid_field_name, parent_field_name, duration_field_name, "cmdb_id"]]
            schema = filtered_df.columns
            schema = schema.drop([traceid_field_name])
            extracted_data = extracted_data + f'\n\n#### {fname}'
            extracted_data = extracted_data + f' Schema: '  + ','.join([s for s in schema if s != col]) + '\n'
            resampled_df = filtered_df.groupby(filtered_df[col] // sample_interval).first()
            trace_ids = resampled_df[traceid_field_name]
            trace_dfs = filtered_df[filtered_df[traceid_field_name].isin(trace_ids)]
            trace_grouped_df = trace_dfs.groupby(traceid_field_name)
            for trace_id, trace_df in trace_grouped_df:
                resource_name = f'{trace_id}'
                for field in trace_df.columns:
                    if trace_df[field].dtype in [float, "float64"]:
                        trace_df[field] = trace_df[field].apply(lambda x: round(x, 2))
                trace_df = trace_df.drop(columns=[traceid_field_name, col])
                if 'group' in trace_df.columns:
                    trace_df = trace_df.drop(columns=["group"])
                if trace_df.empty:
                    extracted_data = extracted_data + f'Trace ID: {resource_name}\n```\n' + "DATA NOT AVAILABLE\n```\n"
                else:
                    data = trace_df.astype(str).agg(','.join, axis=1)
                    extracted_data = extracted_data + f'Trace ID: {resource_name}\n```\n'  + '\n'.join(data) + '\n```\n'
            t3 = time()
            logger.debug(f"{round(t2-t1,1)} seconds for extracting trace data")
        elif data_type == "metric":
            opt_kpi_field_name = ["name", "kpi_name", "serviceName", "tc", "service"]
            kpi_field_name = None
            for opt_name in opt_kpi_field_name:
                if opt_name in df_file.columns:
                    kpi_field_name = opt_name
                    break
            if kpi_field_name==None:
                logger.error("There is no 'name' or 'serviceName' indicating the kpi_name of the data entries")
                raise IndexError
            
            if kpi_field_name == 'name' or kpi_field_name == 'kpi_name':
                if len(filtered_df[kpi_field_name].unique()) > 0:
                    kpi = random.choice(filtered_df[kpi_field_name].unique())
                    while kpi in selected_kpi:
                        kpi = random.choice(filtered_df[kpi_field_name].unique())
                    selected_kpi.add(kpi)
                    filtered_df = filtered_df[filtered_df[kpi_field_name] == kpi]
                else:
                    continue
            elif kpi_field_name == 'serviceName' or kpi_field_name == 'tc' or kpi_field_name == 'service':
                if kpi_field_name not in selected_kpi:
                    selected_kpi.add(kpi_field_name)
                else:
                    continue
            filtered_df["group"] = filtered_df[col].apply(lambda x: x // sample_interval)
            if 'cmdb_id' not in filtered_df.columns:
                filtered_df["resource_name"] = filtered_df[kpi_field_name]
                filtered_df = filtered_df.drop(columns=[kpi_field_name])
            else: 
                filtered_df["resource_name"] = filtered_df["cmdb_id"] + "_" + filtered_df[kpi_field_name]
                filtered_df = filtered_df.drop(columns=["cmdb_id", kpi_field_name])
            if "itemid" in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=["itemid"])
            if "bomc_id" in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=["bomc_id"])
            schema = filtered_df.columns
            schema = schema.drop("resource_name")
            schema = schema.drop('group')
            extracted_data = extracted_data + f'\n\n#### {fname}'
            extracted_data = extracted_data + f' Schema: '  + ','.join([s for s in schema if s != col]) + '\n'
            resource_grouped_df = filtered_df.groupby("resource_name")
            for resource_name, resource_df in resource_grouped_df:
                resampled_df = resource_df.groupby(resource_df[col] // sample_interval).first()
                for field in resampled_df.columns:
                    if resampled_df[field].dtype in [float, "float64"]:
                        resampled_df[field] = resampled_df[field].apply(lambda x: round(x, 2))
                resampled_df = resampled_df.drop(columns=["resource_name"])
                if 'group' in resampled_df.columns:
                    resampled_df = resampled_df.drop(columns=["group"])
                if resampled_df.empty:
                    extracted_data = extracted_data + f'{resource_name}\n```\n' + "DATA NOT AVAILABLE\n```\n"
                resampled_df = resampled_df.drop(columns=[col])
                data = resampled_df.astype(str).agg(','.join, axis=1)
                extracted_data = extracted_data + f'{resource_name}\n```\n'  + '\n'.join(data) + '\n```\n'

            t3 = time()
            logger.debug(f"{round(t3-t2,1)} seconds for selecting metric data")
    return extracted_data, selected_kpi

def main(args):
    import rca.baseline.rca_agent.prompt.agent_prompt as ap
    if args.dataset == "Telecom":
        import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp
    elif args.dataset == "Bank":
        import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp
    elif args.dataset == "Market/cloudbed-1" or args.dataset == "Market/cloudbed-2":
        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp

    inst_file = f"dataset/{args.dataset}/query.csv"
    gt_file = f"dataset/{args.dataset}/record.csv"
    eval_file = f"test/result/{args.dataset}/balanced_{args.tag}_{args.mode}-{configs['MODEL'].split('/')[-1]}.csv"
    obs_path = f"test/monitor/{args.dataset}/balanced_{args.tag}_{args.mode}-{configs['MODEL'].split('/')[-1]}"
    unique_obs_path = f"{obs_path}/{uid}"

    instruct_data = pd.read_csv(inst_file)
    gt_data = pd.read_csv(gt_file)
    if not os.path.exists(inst_file) or not os.path.exists(gt_file):
        raise FileNotFoundError(f"Please download the dataset first.")
    
    if not os.path.exists(f"{unique_obs_path}/prompt"):
        os.makedirs(f"{unique_obs_path}/prompt")
    if not os.path.exists(eval_file):
        if not os.path.exists(f"test/result/{args.dataset}"):
            os.makedirs(f"test/result/{args.dataset}")
        eval_df = pd.DataFrame(columns=["instruction", "prediction", "groundtruth", "passed", "failed", "score"])
    else:
        eval_df = pd.read_csv(eval_file)

    logfile = f"{unique_obs_path}/batch.log"
    logger.remove()
    logger.add(sys.stdout, colorize=True, enqueue=True, level="INFO")
    logger.add(logfile, colorize=True, enqueue=True, level="INFO")
    
    scores = {
        "total": 0,
        "easy": 0,
        "middle": 0,
        "hard": 0,
    }
    nums = {
        "total": 0,
        "easy": 0,
        "middle": 0,
        "hard": 0,
    }
    
    logger.info(f"Using dataset: {args.dataset}")
    logger.info(f"Using model: {configs['MODEL'].split('/')[-1]}")
    logger.info("Start caching dataframes ...")
    df_dict, selected_kpi_len, cand = cache_df_dict(args.dataset)
    
    for idx, row in instruct_data.iterrows():

        if idx < args.start_idx:
                continue
        if idx > args.end_idx:
            break
        
        instruction = row["instruction"]
        timestamp = gt_data.iloc[idx]["timestamp"].astype(int)
        date_time = gt_data.iloc[idx]["datetime"].split(" ")[0].replace("-","_")
        task_index = row["task_index"]
        scoring_points = row["scoring_points"]
        print(scoring_points)
        task_id = int(task_index.split('_')[1])
        best_score = 0

        if task_id <= 3:
            catalog = "easy"
        elif task_id <= 6:
            catalog = "middle"
        elif task_id <= 7:
            catalog = "hard"
            
        

        for i in range(args.sample_num):
            uuid = uid + f"_#{idx}-{i}"
            promptfile = f"{unique_obs_path}/prompt/{uuid}.txt"
            logger.debug('\n' + "#"*80 + f"\n{uuid}: {task_index}\n" + "#"*80)
            
            period_data = dict()
            
            if args.dataset != "Telecom":
                period_data["log"], _ = extract_period_data(deepcopy(df_dict[date_time]["log"]),
                                                        "log", timestamp,
                                                        sample_interval=args.sample_interval,
                                                        )
            
            period_data["trace"], _ = extract_period_data(deepcopy(df_dict[date_time]["trace"]),
                                                        "trace",
                                                        timestamp,
                                                        sample_interval=args.sample_interval,
                                                        )
            
            selected_kpi = set()
            new_kpi = ""
            period_data['metric'] = ""
            logger.info(f"Sampling Started.")
            while len(selected_kpi) < selected_kpi_len:
                new_kpi, selected_kpi = extract_period_data(deepcopy(df_dict[date_time]["metric"]),
                                                                    "metric",
                                                                    timestamp,
                                                                    sample_interval=args.sample_interval,
                                                                    selected_kpi=selected_kpi,
                                                                    selected_kpi_len=selected_kpi_len
                                                                    )
                period_data['metric'] += new_kpi
            logger.info(f"Selected KPI number: {len(selected_kpi)}\tLimit: {selected_kpi_len}")
            
            logger.info(f"Sampling Finished. Total tokens: {sum([len(tokenizer.encode(data)) for data in period_data.values()])}")

            try:   
                if args.mode == "direct":         
                    model = DirectLM(gt_data, cand)
                elif args.mode == "cot":
                    model = CoTLM(gt_data, cand)

                prediction, prompt = model.run(instruction, period_data, args.sample_interval, logger)
                with open (promptfile, 'w') as f:
                    for p in prompt:
                        f.write(str(p['content']))
                    f.write('\n\n')
                    f.write(str(prediction))

                new_eval_df = pd.DataFrame([{"row_id": idx,
                                            "task_index": task_index,
                                            "instruction": instruction, 
                                            "prediction": prediction,
                                            "groundtruth": '\n'.join([f'{col}: {gt_data.iloc[idx][col]}' for col in gt_data.columns if col != 'description']),
                                            "passed": "N/A",
                                            "failed": "N/A", 
                                            "score": "N/A"}])
                eval_df = pd.concat([eval_df, new_eval_df], 
                                    ignore_index=True)
                eval_df.to_csv(eval_file, 
                                index=False)

                if prediction == "EXCEED!":
                    passed_criteria = ["EXCEED!"]
                    failed_criteria = ["EXCEED!"]
                    score = 0.0
                else:
                    passed_criteria, failed_criteria, score = evaluate(prediction, scoring_points)
                logger.info(f"Prediction: {prediction}")
                logger.info(f"Scoring Points: {scoring_points}")
                logger.info(f"Passed Criteria: {passed_criteria}")
                logger.info(f"Failed Criteria: {failed_criteria}")
                logger.info(f"Score: {score}")
                best_score = max(best_score, score)

                eval_df.loc[eval_df.index[-1], "passed"] = '\n'.join(passed_criteria)
                eval_df.loc[eval_df.index[-1], "failed"] = '\n'.join(failed_criteria)
                eval_df.loc[eval_df.index[-1], "score"] = score
                eval_df.to_csv(eval_file, 
                                index=False)
                
                temp_scores = scores.copy()
                temp_scores[catalog] += best_score
                temp_scores["total"] += best_score
                temp_nums = nums.copy()
                temp_nums[catalog] += 1
                temp_nums["total"] += 1
                
            except Exception as e:
                logger.error(e)
                continue
            
        scores = temp_scores
        nums = temp_nums

    
                        
if __name__ == "__main__":
    uid = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="Market/cloudbed-1")
    parser.add_argument("--sample_num", type=int, default=1)
    parser.add_argument("--start_idx", type=int, default=0)
    parser.add_argument("--end_idx", type=int, default=150)
    parser.add_argument("--sample_interval", type=int, default=60)
    parser.add_argument("--mode", type=str, default="direct")
    parser.add_argument("--tag", type=str, default='lm')
    
    args = parser.parse_args()

    main(args)

