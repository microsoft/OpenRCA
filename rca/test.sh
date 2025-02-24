python -m main.evaluate \
    -p \
        rca/archive/agent-Bank.csv \
        rca/archive/agent-Market-cloudbed-1.csv \
        rca/archive/agent-Market-cloudbed-2.csv \
        rca/archive/agent-Telecom.csv \
    -q \
        dataset/Bank/query.csv \
        dataset/Market/cloudbed-1/query.csv \
        dataset/Market/cloudbed-2/query.csv \
        dataset/Telecom/query.csv \
    -r \
        test/agent_claude.csv