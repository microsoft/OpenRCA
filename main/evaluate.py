import sys
import os
import re
import argparse

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, parent_dir)

def evaluate(prediction:str, scoring_points:str):
    """
    Evaluate single JSON-like prediction with corresponding scoring points
        args:
            prediction: str, the prediction (JSON-like string)
            scoring_points: str, the scoring points string
    """

    import itertools

    predict_pattern = (
        r'{\s*'
        r'(?:"root cause occurrence datetime":\s*"(.*?)")?,?\s*'
        r'(?:"root cause component":\s*"(.*?)")?,?\s*'
        r'(?:"root cause reason":\s*"(.*?)")?\s*}'
    )

    predict_matches = re.findall(predict_pattern, prediction)


    predict_results = []
    
    for match in predict_matches:
        datetime_str, component, reason = match
        predict_results.append({
            "root cause occurrence datetime": datetime_str,
            "root cause component": component,
            "root cause reason": reason
        })



    prediction_length = len(predict_results)

    component_pattern = r"The (?:\d+-th|only) predicted root cause component is ([^\n]+)"
    reason_pattern = r"The (?:\d+-th|only) predicted root cause reason is ([^\n]+)"
    time_pattern = r"The (?:\d+-th|only) root cause occurrence time is within 1 minutes \(i.e., <=1min\) of ([^\n]+)"

    components = re.findall(component_pattern, scoring_points)
    reasons = re.findall(reason_pattern, scoring_points)
    times = re.findall(time_pattern, scoring_points)

    scoringpoints_length = max(len(components),len(reasons),len(times))
    socres_num = len(components)+len(reasons)+len(times)

    def time_difference(time1_str,time2_str):
        from datetime import datetime
        time_format = "%Y-%m-%d %H:%M:%S"
        
        try:
            time1 = datetime.strptime(time1_str, time_format)
            time2 = datetime.strptime(time2_str, time_format)
        except ValueError:
            return False
        
        time_difference = abs(time1 - time2)
        if time_difference.total_seconds() <= 60:
            return True
        else:
            return False

    scores_get = 0
    passing_criteria = []
    failing_criteria = []

    if scoringpoints_length == prediction_length:  
        best_sore = -1
        for perm in itertools.permutations(predict_results):
            current_score = 0
            current_passing = []
            for i in range(scoringpoints_length):
                if len(components) == scoringpoints_length:
                    if perm[i]['root cause component'] == components[i]:
                        current_score +=1
                        current_passing.append(components[i])
                if len(reasons) == scoringpoints_length:
                    if perm[i]['root cause reason'] == reasons[i]:
                        current_score +=1
                        current_passing.append(reasons[i])
                if len(times) == scoringpoints_length:
                    if time_difference(times[i],perm[i]['root cause occurrence datetime']):
                        current_score +=1
                        current_passing.append(times[i])
            if current_score>best_sore:
                best_sore = current_score
                passing_criteria = current_passing
        scores_get = best_sore            
    
    failing_criteria = list(set(components+reasons+times)-set(passing_criteria))
    
    final_score = scores_get/socres_num
    bin_score = round(final_score,2)
    return passing_criteria, failing_criteria, bin_score


def file_evaluate(prediction_file:str, query_file:str, report_file:str):
    """
    Evaluate a prediction file of certain dataset with corresponding query file and save the evaluation results to a csv file
        args:
            prediction_file: str, the path of the prediction file (csv, with at least one fields: 'prediction')
            query_file: str, the path of a specific dataset recorded labels (csv)
            report_file: str, the path of the evaluation file (csv)
    """ 
    import pandas as pd

    pred_df = pd.read_csv(prediction_file)
    query_df = pd.read_csv(query_file)
    eval_df = pd.DataFrame(columns=["query", "answer", "groundtruth", "passed", "failed", "score", "task_index"])

    if len(pred_df) != len(query_df):
        raise ValueError("The length of prediction file and record file should be the same")

    for idx in range(len(pred_df)):
        prediction = pred_df.loc[idx, "prediction"]
        scoring_points = query_df.loc[idx, "scoring_points"]
        passing_criteria, failing_criteria, score = evaluate(prediction, scoring_points)
        instruction = query_df.loc[idx, "instruction"]
        task_index = query_df.loc[idx, "task_index"]
        new_row = pd.DataFrame({
            "query": [instruction], 
            "answer": [prediction], 
            "groundtruth": [scoring_points], 
            "passed": [passing_criteria], 
            "failed": [failing_criteria], 
            "score": [score], 
            "task_index": [task_index]
        })
        eval_df = pd.concat([eval_df, new_row], ignore_index=True)


    if os.path.exists(report_file):
        eval_df.to_csv(report_file, mode='a', header=False, index=False)
    else:
        eval_df.to_csv(report_file, index=False)


def report(report_file):
    """
    Visualize the final result of a report after evaluation
        args:
            report_file: str, report after evaluation
    """
    import pandas as pd

    scores = {
        "easy": 0,
        "middle": 0,
        "hard": 0,
    }
    nums = {
        "easy": 0,
        "middle": 0,
        "hard": 0,
    }

    df = pd.read_csv(report_file)
    # By default, task_1-3 is easy, task_4-6 is middle, task_7 is hard. For DIY task specifications, you should change this line to modify the difficulty:
    df["difficulty"] = df["task_index"].apply(lambda x: "easy" if int(x.split('_')[1]) <= 3 else "middle" if int(x.split('_')[1]) <= 6 else "hard")
    scores['easy'] += len(df[(df["score"]==1.0) & (df["difficulty"]=="easy")])
    scores['middle'] += len(df[(df["score"]==1.0) & (df["difficulty"]=="middle")])
    scores['hard'] += len(df[(df["score"]==1.0) & (df["difficulty"]=="hard")])
    nums['easy'] += len(df[df["difficulty"]=="easy"])
    nums['middle'] += len(df[df["difficulty"]=="middle"])
    nums['hard'] += len(df[df["difficulty"]=="hard"])

    print(f"{'-'*12:<12}{'-'*12:<12}{'-'*12:<12}{'-'*12}")
    print(f"{'Class':<12}{'Total(#)':<12}{'Correct(#)':<12}{'Accuracy(%)':<12}")
    print(f"{'-'*12:<12}{'-'*12:<12}{'-'*12:<12}{'-'*12}")
    for key in scores.keys():
        accuracy = scores[key] / nums[key] if nums[key] > 0 else 0
        print(f"{key:<12}{nums[key]:<12}{scores[key]:<12}{accuracy:.2%}")
    print(f"{'-'*12:<12}{'-'*12:<12}{'-'*12:<12}{'-'*12}")
    total_accuracy = sum(scores.values()) / sum(nums.values()) if sum(nums.values()) > 0 else 0
    print(f"{'Total':<12}{sum(nums.values()):<12}{sum(scores.values()):<12}{total_accuracy:.2%}")
    print(f"{'-'*12:<12}{'-'*12:<12}{'-'*12:<12}{'-'*12}")
    



if __name__ == '__main__':
    """
    Evaluate a list of prediction files with corresponding query files, save the evaluation results, and display the statistic results.
        args:
            p: list, a list of prediction files to evaluate
            q: list, a list of query files to evaluate
            r: str, report file to save
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=str, nargs='+', help="a list of prediction files to evaluate")
    parser.add_argument("-q", type=str, nargs='+', help="a list of query files to evaluate")
    parser.add_argument("-r", type=str, help="evaluation file to save")
    args = parser.parse_args()

    if len(args.p) != len(args.q):
        raise ValueError("The length of prediction files, query files and evaluation files should be the same")
    if os.path.exists(args.r):
        os.remove(args.r)
    
    for i in range(len(args.p)):
        try:
            file_evaluate(args.p[i], args.q[i], args.r)
        except Exception as e:
            print(f"Error when evaluating the file {args.p[i]}: {e}")
            continue
    
    report(args.r)