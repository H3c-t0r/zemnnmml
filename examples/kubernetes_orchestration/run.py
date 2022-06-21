from pipelines.kubernetes_example_pipeline import kubernetes_example_pipeline
from steps import evaluator, importer, skew_comparison, svc_trainer

if __name__ == "__main__":
    kubernetes_example_pipeline(
        importer=importer(),
        trainer=svc_trainer(),
        evaluator=evaluator(),
        skew_comparison=skew_comparison(),
    ).run()

    # In case you want to run this on a schedule, run it in the following way:
    #
    # from zenml.pipelines import Schedule
    #
    # schedule = Schedule(cron_expression="*/5 * * * *")  # every 5 minutes
    #
    # kubernetes_example_pipeline(
    #     importer=importer(),
    #     trainer=svc_trainer(),
    #     evaluator=evaluator(),
    #     skew_comparison=skew_comparison(),
    # ).run(schedule=schedule)
