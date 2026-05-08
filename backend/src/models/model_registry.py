import mlflow
from mlflow.tracking import MlflowClient
import logging

logger = logging.getLogger(__name__)

def shadow_deployment_update(experiment_name="fraud-detection-xgboost", 
                             model_name="fraud_xgboost_model", 
                             metric_to_compare="pr_auc"):
    """
    Implements a Champion/Challenger (Shadow Deployment) logic.
    Finds the best run in the current experiment, registers it,
    and transitions it to Staging (Challenger) or Production (Champion)
    based on whether it beats the current production model.
    """
    client = MlflowClient()
    
    experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id
    if not experiment_id:
        logger.error(f"Experiment {experiment_name} not found.")
        return

    # Find the best run based on the given metric
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        order_by=[f"metrics.{metric_to_compare} DESC"],
        max_results=1
    )
    
    if not runs:
        logger.info("No runs found to promote.")
        return
        
    best_run = runs[0]
    best_run_id = best_run.info.run_id
    best_metric = best_run.data.metrics.get(metric_to_compare, 0)
    
    logger.info(f"Best run found: {best_run_id} with {metric_to_compare} = {best_metric:.4f}")

    # Register the best model (creates a new version)
    model_uri = f"runs:/{best_run_id}/xgb_model"
    try:
        mv = mlflow.register_model(model_uri, model_name)
        new_version = mv.version
        logger.info(f"Registered model {model_name} version {new_version}")
    except Exception as e:
        logger.warning(f"Could not register model: {e}")
        return

    # Fetch current Production model (the Champion)
    try:
        prod_versions = client.get_latest_versions(model_name, stages=["Production"])
    except Exception:
        prod_versions = []

    if prod_versions:
        prod_version = prod_versions[0]
        prod_run_id = prod_version.run_id
        
        # We need to fetch the PR-AUC of the production model
        try:
            prod_run = client.get_run(prod_run_id)
            prod_metric = prod_run.data.metrics.get(metric_to_compare, 0)
        except Exception:
            prod_metric = 0

        logger.info(f"Current Champion (Production, v{prod_version.version}) {metric_to_compare} = {prod_metric:.4f}")

        if best_metric > prod_metric:
            logger.info("Challenger beats Champion! Promoting to Production.")
            # Transition old prod to Archived
            client.transition_model_version_stage(
                name=model_name,
                version=prod_version.version,
                stage="Archived"
            )
            # Transition new to Prod
            client.transition_model_version_stage(
                name=model_name,
                version=new_version,
                stage="Production"
            )
        else:
            logger.info("Challenger did not beat Champion. Sending to Staging for Shadow Mode.")
            client.transition_model_version_stage(
                name=model_name,
                version=new_version,
                stage="Staging"
            )
    else:
        logger.info("No existing Production model found. Promoting directly to Production.")
        client.transition_model_version_stage(
            name=model_name,
            version=new_version,
            stage="Production"
        )
