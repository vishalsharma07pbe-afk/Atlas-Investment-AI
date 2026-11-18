// @vitest-environment jsdom
import {fireEvent,render,screen} from "@testing-library/react";
import {describe,expect,it,vi} from "vitest";
import ExchangePicker from "./ExchangePicker";

describe("ExchangePicker",()=>{
  it("shows the active market and reports a new selection",()=>{
    const onChange=vi.fn();
    render(<ExchangePicker value="" onChange={onChange} label="Market exchange"/>);
    expect(screen.getByRole("button",{name:"All"}).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button",{name:"NSE"}));
    expect(onChange).toHaveBeenCalledWith("NSE");
  });
});
