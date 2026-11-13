"""Read-only comparison of independent, hypothetical goal scenarios."""
from pydantic import BaseModel,Field,model_validator
from .goal_planning import GoalRequest,goal_projection

class NamedScenario(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    parameters:GoalRequest

class ComparisonRequest(BaseModel):
    scenarios:list[NamedScenario]=Field(min_length=2,max_length=5)
    @model_validator(mode="after")
    def unique_names(self):
        names=[s.name.strip().casefold() for s in self.scenarios]
        if len(set(names))!=len(names):
            raise ValueError("Scenario names must be unique")
        return self

def compare_scenarios(request:ComparisonRequest)->dict:
    results=[]
    for scenario in request.scenarios:
        projection=goal_projection(scenario.parameters)
        results.append({"name":scenario.name.strip(),**projection})
    return {"status":"ILLUSTRATIVE_COMPARISON","scenarios":results,
        "notice":"Scenarios use independently assumed fixed returns. No likelihood ranking, historical backtest, live data, tax estimate or investment recommendation."}
