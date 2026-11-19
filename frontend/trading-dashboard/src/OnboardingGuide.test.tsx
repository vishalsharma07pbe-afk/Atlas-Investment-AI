/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import OnboardingGuide from "./OnboardingGuide";

afterEach(()=>{cleanup();localStorage.clear();});

it("guides keyboard-accessible navigation and remembers completion",()=>{
 const navigate=vi.fn();
 render(<OnboardingGuide onNavigate={navigate}/>);
 expect(screen.getByText("Add what you own")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Open this area"}));
 expect(navigate).toHaveBeenCalledWith(0);
 fireEvent.click(screen.getByRole("button",{name:"Next"}));
 expect(screen.getByText("Check the evidence")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Next"}));
 fireEvent.click(screen.getByRole("button",{name:"Finish setup"}));
 expect(localStorage.getItem("atlas:onboarding-complete:v1")).toBe("true");
 expect(screen.queryByText("Research, do not trade blindly")).toBeNull();
});

