/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen,fireEvent,waitFor} from "@testing-library/react";
import GoalMonitor from "./GoalMonitor";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const goal={id:"goal-1",name:"Car deposit",targetAmount:100000,reservedAmount:40000,balanceDate:"2026-11-25",deadline:"2027-02-15",monthlyContribution:15000,
 progress:{status:"FUNDING_SHORTFALL",remainingMonthEnds:3,recordedProgressPercent:40,recordedGap:60000,zeroGrowthProjectedBalance:85000,zeroGrowthShortfall:15000,requiredMonthlyContribution:20000,additionalMonthlyContribution:5000}};
const report={as_of:"2026-11-25",goals:[goal],notice:"Explicitly reserved balances only."};
it("automatically shows funding gaps from saved goals without calculator input",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>report})));
 render(<GoalMonitor/>);
 expect(await screen.findByText("Car deposit")).toBeTruthy();
 expect(screen.getByText("Funding shortfall")).toBeTruthy();
 expect(screen.getByText("₹20,000")).toBeTruthy();
 expect(screen.getByText("Explicitly reserved balances only.",{exact:false})).toBeTruthy();
 expect(screen.getByRole("progressbar",{name:"Car deposit recorded progress"}).getAttribute("value")).toBe("40");
});
it("updates the explicitly recorded balance and refreshes after saving",async()=>{
 const fetchMock=vi.fn(async(_url:string,options?:RequestInit)=>options?.method==="PUT"?{ok:true,json:async()=>({saved:true})}:{ok:true,json:async()=>report});
 vi.stubGlobal("fetch",fetchMock);
 render(<GoalMonitor/>);
 fireEvent.click(await screen.findByRole("button",{name:"Update goal / balance"}));
 fireEvent.change(screen.getByLabelText("Reserved amount (INR)"),{target:{value:"50000"}});
 fireEvent.click(screen.getByRole("button",{name:"Save goal"}));
 await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith("/api/v1/portfolio/goals/goal-1",expect.objectContaining({method:"PUT",body:expect.stringContaining('"reservedAmount":"50000"')})));
 await waitFor(()=>expect(fetchMock.mock.calls.filter(c=>!c[1]?.method)).toHaveLength(2));
});
it("does not display projected funding values for stale balances",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({...report,goals:[{...goal,progress:{...goal.progress,status:"STALE_RECORDED_BALANCE",zeroGrowthProjectedBalance:null,zeroGrowthShortfall:null,requiredMonthlyContribution:null,additionalMonthlyContribution:null}}]})})));
 render(<GoalMonitor/>);
 expect(await screen.findByText("Update recorded balance")).toBeTruthy();
 expect(screen.getAllByText("Unavailable",{exact:false}).length).toBeGreaterThanOrEqual(3);
 expect(screen.queryByText("₹20,000")).toBeNull();
});
