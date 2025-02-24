import os
import sys
import json
import argparse
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
from main.evaluate import evaluate
from rca.api_router import configs

from datetime import datetime
from loguru import logger
from nbformat import v4 as nbf
import pandas as pd
import signal

def handler(signum, frame):
    raise TimeoutError("Loop execution exceeded the time limit")

def main(args, uid, dataset):

    from rca.baseline.rca_agent.rca_agent import RCA_Agent
    import rca.baseline.rca_agent.prompt.agent_prompt as ap
    if dataset == "Telecom":
        import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp
    elif dataset == "Bank":
        import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp
    elif dataset == "Market/cloudbed-1" or dataset == "Market/cloudbed-2":
        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp

    inst_file = f"dataset/{dataset}/query.csv"
    gt_file = f"dataset/{dataset}/record.csv"
    eval_file = f"test/result/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}.csv"
    obs_path = f"test/monitor/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}"
    unique_obs_path = f"{obs_path}/{uid}"

    instruct_data = pd.read_csv(inst_file)
    gt_data = pd.read_csv(gt_file)
    if not os.path.exists(inst_file) or not os.path.exists(gt_file):
        raise FileNotFoundError(f"Please download the dataset first.")

    if not os.path.exists(f"{unique_obs_path}/history"):
        os.makedirs(f"{unique_obs_path}/history")
    if not os.path.exists(f"{unique_obs_path}/trajectory"):
        os.makedirs(f"{unique_obs_path}/trajectory")
    if not os.path.exists(f"{unique_obs_path}/prompt"):
        os.makedirs(f"{unique_obs_path}/prompt")
    if not os.path.exists(eval_file):
        if not os.path.exists(f"test/result/{dataset}"):
            os.makedirs(f"test/result/{dataset}")
        eval_df = pd.DataFrame(columns=["instruction", "prediction", "groundtruth", "passed", "failed", "score"])
    else:
        eval_df = pd.read_csv(eval_file)

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

    signal.signal(signal.SIGALRM, handler)
    logger.info(f"Using dataset: {dataset}")
    logger.info(f"Using model: {configs['MODEL'].split('/')[-1]}")
    
    for idx, row in instruct_data.iterrows():

        if idx < args.start_idx:
                continue
        if idx > args.end_idx:
            break
        
        instruction = row["instruction"]
        task_index = row["task_index"]
        scoring_points = row["scoring_points"]
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
            nb = nbf.new_notebook()
            nbfile = f"{unique_obs_path}/trajectory/{uuid}.ipynb"
            promptfile = f"{unique_obs_path}/prompt/{uuid}.json"
            logfile = f"{unique_obs_path}/history/{uuid}.log"
            logger.remove()
            logger.add(sys.stdout, colorize=True, enqueue=True, level="INFO")
            logger.add(logfile, colorize=True, enqueue=True, level="INFO")
            logger.debug('\n' + "#"*80 + f"\n{uuid}: {task_index}\n" + "#"*80)
            try: 
                signal.alarm(args.timeout)

                agent = RCA_Agent(ap, bp)
                prediction, trajectory, prompt = agent.run(instruction, 
                                                       logger, 
                                                       max_step=args.controller_max_step, 
                                                       max_turn=args.controller_max_turn)
                
                signal.alarm(0)

                for step in trajectory:
                    code_cell = nbf.new_code_cell(step['code'])
                    result_cell = nbf.new_markdown_cell(f"```\n{step['result']}\n```")
                    nb.cells.append(code_cell)
                    nb.cells.append(result_cell)
                with open(nbfile, 'w', encoding='utf-8') as f:
                    json.dump(nb, f, ensure_ascii=False, indent=4)
                logger.info(f"Trajectory has been saved to {nbfile}")

                with open(promptfile, 'w', encoding='utf-8') as f:
                    json.dump({"messages": prompt}, f, ensure_ascii=False, indent=4)
                logger.info(f"Prompt has been saved to {promptfile}")

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

            except TimeoutError:
                logger.error(f"Loop {i} exceeded the time limit and was skipped")
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
    parser.add_argument("--controller_max_step", type=int, default=25)
    parser.add_argument("--controller_max_turn", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--tag", type=str, default='rca')
    parser.add_argument("--auto", type=bool, default=False)

    args = parser.parse_args()

    if args.auto:
        print(f"Auto mode is on. Model is fixed to {configs['MODEL']}")
        datasets = ["Market/cloudbed-1", "Market/cloudbed-2", "Bank", "Telecom"]
        for dataset in datasets:
            main(args, uid, dataset)
    else:
        dataset = args.dataset
        main(args, uid, dataset)