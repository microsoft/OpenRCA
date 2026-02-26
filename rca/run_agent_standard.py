import os
import sys
import json
import yaml
import argparse
import multiprocessing
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


def _get_prompt_modules(dataset):
    from rca.baseline.rca_agent.rca_agent import RCA_Agent
    import rca.baseline.rca_agent.prompt.agent_prompt as ap
    if dataset == "Telecom":
        import rca.baseline.rca_agent.prompt.basic_prompt_Telecom as bp
    elif dataset == "Bank":
        import rca.baseline.rca_agent.prompt.basic_prompt_Bank as bp
    elif dataset == "Market/cloudbed-1" or dataset == "Market/cloudbed-2":
        import rca.baseline.rca_agent.prompt.basic_prompt_Market as bp
    return RCA_Agent, ap, bp


def process_query(query_args):
    """Process a single query in its own process. Top-level function for pickling."""
    idx, instruction, task_index, scoring_points, gt_columns, dataset, uid, unique_obs_path, timeout, controller_max_step, controller_max_turn, sample_num = query_args

    signal.signal(signal.SIGALRM, handler)
    RCA_Agent, ap, bp = _get_prompt_modules(dataset)

    task_id = int(task_index.split('_')[1])
    best_score = 0
    results = []

    if task_id <= 3:
        catalog = "easy"
    elif task_id <= 6:
        catalog = "middle"
    else:
        catalog = "hard"

    for i in range(sample_num):
        uuid = uid + f"_#{idx}-{i}"
        nb = nbf.new_notebook()
        nbfile = f"{unique_obs_path}/trajectory/{uuid}.ipynb"
        promptfile = f"{unique_obs_path}/prompt/{uuid}.json"
        logfile = f"{unique_obs_path}/history/{uuid}.log"

        proc_logger = logger.bind()
        proc_logger.remove()
        proc_logger.add(sys.stdout, colorize=True, enqueue=True, level="INFO")
        proc_logger.add(logfile, colorize=True, enqueue=True, level="INFO")
        proc_logger.debug('\n' + "#"*80 + f"\n{uuid}: {task_index}\n" + "#"*80)

        try:
            signal.alarm(timeout)

            agent = RCA_Agent(ap, bp)
            prediction, trajectory, prompt = agent.run(instruction,
                                                       proc_logger,
                                                       max_step=controller_max_step,
                                                       max_turn=controller_max_turn)

            signal.alarm(0)

            for step in trajectory:
                code_cell = nbf.new_code_cell(step['code'])
                result_cell = nbf.new_markdown_cell(f"```\n{step['result']}\n```")
                nb.cells.append(code_cell)
                nb.cells.append(result_cell)
            with open(nbfile, 'w', encoding='utf-8') as f:
                json.dump(nb, f, ensure_ascii=False, indent=4)
            proc_logger.info(f"Trajectory has been saved to {nbfile}")

            with open(promptfile, 'w', encoding='utf-8') as f:
                json.dump({"messages": prompt}, f, ensure_ascii=False, indent=4)
            proc_logger.info(f"Prompt has been saved to {promptfile}")

            passed_criteria, failed_criteria, score = evaluate(prediction, scoring_points)

            proc_logger.info(f"Prediction: {prediction}")
            proc_logger.info(f"Scoring Points: {scoring_points}")
            proc_logger.info(f"Passed Criteria: {passed_criteria}")
            proc_logger.info(f"Failed Criteria: {failed_criteria}")
            proc_logger.info(f"Score: {score}")
            best_score = max(best_score, score)

            results.append({
                "row_id": idx,
                "task_index": task_index,
                "instruction": instruction,
                "prediction": prediction,
                "groundtruth": gt_columns,
                "passed": '\n'.join(passed_criteria),
                "failed": '\n'.join(failed_criteria),
                "score": score,
            })

        except TimeoutError:
            proc_logger.error(f"Loop {i} exceeded the time limit and was skipped")
            continue
        except Exception as e:
            proc_logger.error(f"Loop {i} failed with error: {e}")
            continue

    return {
        "idx": idx,
        "catalog": catalog,
        "best_score": best_score,
        "results": results,
    }


def main(args, uid, dataset):

    inst_file = f"dataset/{dataset}/query.csv"
    gt_file = f"dataset/{dataset}/record.csv"
    eval_file = f"test/result/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}.csv"
    obs_path = f"test/monitor/{dataset}/agent-{args.tag}-{configs['MODEL'].split('/')[-1]}"
    unique_obs_path = f"{obs_path}/{uid}"

    instruct_data = pd.read_csv(inst_file)
    gt_data = pd.read_csv(gt_file)
    if not os.path.exists(inst_file) or not os.path.exists(gt_file):
        raise FileNotFoundError(f"Please download the dataset first.")

    os.makedirs(f"{unique_obs_path}/history", exist_ok=True)
    os.makedirs(f"{unique_obs_path}/trajectory", exist_ok=True)
    os.makedirs(f"{unique_obs_path}/prompt", exist_ok=True)
    if not os.path.exists(eval_file):
        os.makedirs(f"test/result/{dataset}", exist_ok=True)
        eval_df = pd.DataFrame(columns=["instruction", "prediction", "groundtruth", "passed", "failed", "score"])
    else:
        eval_df = pd.read_csv(eval_file)

    scores = {"total": 0, "easy": 0, "middle": 0, "hard": 0}
    nums = {"total": 0, "easy": 0, "middle": 0, "hard": 0}

    # Determine already-completed row_ids for resume
    completed_ids = set()
    if "row_id" in eval_df.columns:
        completed_ids = set(eval_df["row_id"].dropna().astype(int).tolist())
        # Re-tally scores from existing results
        for _, existing_row in eval_df.iterrows():
            if "task_index" in existing_row and "score" in existing_row:
                try:
                    tid = int(str(existing_row["task_index"]).split('_')[1])
                    s = float(existing_row["score"])
                except (ValueError, IndexError):
                    continue
                cat = "easy" if tid <= 3 else "middle" if tid <= 6 else "hard"
                scores[cat] += s
                scores["total"] += s
                nums[cat] += 1
                nums["total"] += 1

    logger.info(f"Using dataset: {dataset}")
    logger.info(f"Using model: {configs['MODEL'].split('/')[-1]}")
    if completed_ids:
        logger.info(f"Resuming: {len(completed_ids)} queries already completed, skipping them")

    # Build list of query args, skipping completed
    query_args_list = []
    for idx, row in instruct_data.iterrows():
        if idx < args.start_idx:
            continue
        if idx > args.end_idx:
            break
        if idx in completed_ids:
            continue
        gt_columns = '\n'.join([f'{col}: {gt_data.iloc[idx][col]}' for col in gt_data.columns if col != 'description'])
        query_args_list.append((
            idx,
            row["instruction"],
            row["task_index"],
            row["scoring_points"],
            gt_columns,
            dataset,
            uid,
            unique_obs_path,
            args.timeout,
            args.controller_max_step,
            args.controller_max_turn,
            args.sample_num,
        ))

    if args.workers <= 1:
        # Sequential — same as original behavior
        signal.signal(signal.SIGALRM, handler)
        RCA_Agent, ap, bp = _get_prompt_modules(dataset)

        for qa in query_args_list:
            idx = qa[0]
            instruction = qa[1]
            task_index = qa[2]
            scoring_points = qa[3]
            gt_columns = qa[4]
            task_id = int(task_index.split('_')[1])
            best_score = 0

            if task_id <= 3:
                catalog = "easy"
            elif task_id <= 6:
                catalog = "middle"
            else:
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
                                                "groundtruth": gt_columns,
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
    else:
        # Parallel execution
        total = len(query_args_list)
        logger.info(f"Running {total} queries with {args.workers} workers")
        completed = 0

        with multiprocessing.Pool(processes=args.workers) as pool:
            for result in pool.imap_unordered(process_query, query_args_list):
                completed += 1
                catalog = result["catalog"]
                best_score = result["best_score"]

                scores[catalog] += best_score
                scores["total"] += best_score
                nums[catalog] += 1
                nums["total"] += 1

                for r in result["results"]:
                    new_eval_df = pd.DataFrame([r])
                    eval_df = pd.concat([eval_df, new_eval_df], ignore_index=True)

                eval_df.to_csv(eval_file, index=False)
                logger.info(f"Progress: {completed}/{total} queries completed (idx={result['idx']}, score={best_score})")

    logger.info(f"Final scores: {scores}")
    logger.info(f"Final nums: {nums}")


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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--source", type=str, default=None, help="Override SOURCE (OpenAI, Anthropic, Google, AI)")
    parser.add_argument("--model", type=str, default=None, help="Override MODEL")
    parser.add_argument("--api_key", type=str, default=None, help="Override API_KEY")
    parser.add_argument("--api_base", type=str, default=None, help="Override API_BASE")
    parser.add_argument("--profile", type=str, default=None, help="Load a named profile from rca/api_profiles.yaml")

    args = parser.parse_args()

    if args.profile:
        with open("rca/api_profiles.yaml", "r") as f:
            profiles = yaml.safe_load(f)
        if args.profile not in profiles:
            raise ValueError(f"Profile '{args.profile}' not found. Available: {list(profiles.keys())}")
        for k, v in profiles[args.profile].items():
            configs[k] = v
    if args.source:
        configs["SOURCE"] = args.source
    if args.model:
        configs["MODEL"] = args.model
    if args.api_key:
        configs["API_KEY"] = args.api_key
    if args.api_base:
        configs["API_BASE"] = args.api_base

    if args.auto:
        print(f"Auto mode is on. Model is fixed to {configs['MODEL']}")
        datasets = ["Market/cloudbed-1", "Market/cloudbed-2", "Bank", "Telecom"]
        for dataset in datasets:
            main(args, uid, dataset)
    else:
        dataset = args.dataset
        main(args, uid, dataset)
