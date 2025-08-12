from src.llm_models import openai_o3
DOM_MAP = """
    [0]<a />
    [1]<a DAGs/>
    [2]<a Cluster Activity/>
    [3]<a Datasets/>
    [4]<a Security/>
    [5]<a Browse/>
    [6]<a Admin/>
    [7]<a Docs/>
    [8]<a 15:25
    UTC/>
    [9]<a UU/>
    [10]<button ×/>
    Recent requests have been made to /robots.txt. This indicates that this deployment may be accessible to the public internet. This warning can be disabled by setting webserver.warn_deployment_exposure=False in airflow.cfg. Read more about web deployment security
    [11]<a here/>
    [12]<div tab/>
    [13]<a ;button>error
    DAG Import Errors (2)
    expand_less/>
    The scheduler does not appear to be running.
        
        Last heartbeat was received
    2 days ago
    .
    The DAGs list may not update, and new tasks will not be scheduled.
    Do not use
    SQLite
    as metadata DB in production – it should only be used for dev/testing.
        We recommend using Postgres or MySQL.
    [14]<a Click here/>
    for more information.
    Do not use the
    SequentialExecutor
    in production.
    [15]<a Click here/>
    for more information.
    DAGs
    [16]<a All
    51/>
    [17]<a Active
    0/>
    [18]<a Paused
    51/>
    [19]<a Running
    0/>
    [20]<a Failed
    0/>
    [21]<span combobox/>
    [22]<input searchbox;Filter DAGs by tag;search/>
    Search DAGs
    [23]<input Search DAGs;search/>
    Auto-refresh
    [24]<button refresh/>
    info
    [25]<a ;tooltip>DAG
    unfold_more/>
    [26]<a ;tooltip>Owner
    unfold_more/>
    Runs
    info
    Schedule
    [27]<a ;tooltip>Last Run
    unfold_more/>
    info
    [28]<a ;tooltip>Next Run
    unfold_more/>
    info
    Recent Tasks
    info
    Actions
    Links
    [29]<a admin_only_hello_world/>
    [30]<a admin-only/>
    [31]<a example/>
    [32]<a airflow/>
    [33]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [34]<a ;Trigger DAG>play_arrow/>
    [35]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [36]<a dataset_consumes_1/>
    [37]<a consumes/>
    [38]<a dataset-scheduled/>
    [39]<a airflow/>
    [40]<a Dataset/>
    info
    On s3://dag1/output_1.txt
    [41]<a ;Trigger DAG>play_arrow/>
    [42]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [43]<a dataset_consumes_1_and_2/>
    [44]<a consumes/>
    [45]<a dataset-scheduled/>
    [46]<a airflow/>
    [47]<a Dataset/>
    info
    0 of 2 datasets updated
    [48]<a ;Trigger DAG>play_arrow/>
    [49]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [50]<a dataset_consumes_1_never_scheduled/>
    [51]<a consumes/>
    [52]<a dataset-scheduled/>
    [53]<a airflow/>
    [54]<a Dataset/>
    info
    0 of 2 datasets updated
    [55]<a ;Trigger DAG>play_arrow/>
    [56]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [57]<a dataset_consumes_unknown_never_scheduled/>
    [58]<a dataset-scheduled/>
    [59]<a airflow/>
    [60]<a Dataset/>
    info
    0 of 2 datasets updated
    [61]<a ;Trigger DAG>play_arrow/>
    [62]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [63]<a dataset_produces_1/>
    [64]<a dataset-scheduled/>
    [65]<a produces/>
    [66]<a airflow/>
    [67]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [68]<a ;Trigger DAG>play_arrow/>
    [69]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [70]<a dataset_produces_2/>
    [71]<a dataset-scheduled/>
    [72]<a produces/>
    [73]<a airflow/>
    [74]<a None/>
    info
    [75]<a ;Trigger DAG>play_arrow/>
    [76]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [77]<input checkbox/>
    [78]<a example_bash_operator/>
    [79]<a example/>
    [80]<a example2/>
    [81]<a airflow/>
    [82]<a 0 0 * * */>
    info
    2025-08-08, 00:00:00
    info
    [83]<a ;Trigger DAG>play_arrow/>
    [84]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [85]<input checkbox/>
    [86]<a example_branch_datetime_operator/>
    [87]<a example/>
    [88]<a airflow/>
    [89]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [90]<a ;Trigger DAG>play_arrow/>
    [91]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [92]<input checkbox/>
    [93]<a example_branch_datetime_operator_2/>
    [94]<a example/>
    [95]<a airflow/>
    [96]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [97]<a ;Trigger DAG>play_arrow/>
    [98]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [99]<input checkbox/>
    [100]<a example_branch_datetime_operator_3/>
    [101]<a example/>
    [102]<a airflow/>
    [103]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [104]<a ;Trigger DAG>play_arrow/>
    [105]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [106]<input checkbox/>
    [107]<a example_branch_dop_operator_v3/>
    [108]<a example/>
    [109]<a airflow/>
    [110]<a */1 * * * */>
    info
    2025-08-09, 06:50:00
    info
    [111]<a ;Trigger DAG>play_arrow/>
    [112]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [113]<input checkbox/>
    [114]<a example_branch_labels/>
    [115]<a airflow/>
    [116]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [117]<a ;Trigger DAG>play_arrow/>
    [118]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [119]<input checkbox/>
    [120]<a example_branch_operator/>
    [121]<a example/>
    [122]<a example2/>
    [123]<a airflow/>
    [124]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [125]<a ;Trigger DAG>play_arrow/>
    [126]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [127]<input checkbox/>
    [128]<a example_branch_python_operator_decorator/>
    [129]<a example/>
    [130]<a example2/>
    [131]<a airflow/>
    [132]<a @daily/>
    info
    2025-08-08, 00:00:00
    info
    [133]<a ;Trigger DAG>play_arrow/>
    [134]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
    [135]<input checkbox/>
    [136]<a example_complex/>
    [137]<a example/>
    [138]<a example2/>
    [139]<a example3/>
    [140]<a airflow/>
    [141]<a None/>
    info
    [142]<a ;Trigger DAG>play_arrow/>
    [143]<a ;Delete DAG>delete_outline/>
    code
    Code
    vertical_distribute
    Gantt
    flight_land
    Landing
    repeat
    Tries
    hourglass_bottom
    Duration
    event
    Calendar
    account_tree
    Graph
    grid_on
    Grid
    more_horiz
"""
PROMPT = """
{dom_map}

You are given a compressed representation of the DOM of a webpage.
Your goal is to come up with a plan for exploring the webpage.

First sort the interactions into three categories:
1. Navigation: these are navigational links that will take you to a new page
2. Write API: these are APIs that change the state of the app
3. Read API: these are APIs that do not 
"""

model = openai_o3()
