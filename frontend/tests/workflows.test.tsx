// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ScheduleHistory from "../src/components/ScheduleHistory";
import AssignmentEditor from "../src/components/AssignmentEditor";
import RunPanel from "../src/components/RunPanel";
import * as api from "../src/api/client";

vi.mock("../src/api/client", () => ({
  listScheduleVersions: vi.fn(), publishScheduleVersion: vi.fn(), loadScheduleVersion: vi.fn(),
  adjustScheduleVersion: vi.fn(), regenerateScheduleVersion: vi.fn(),
  deleteScheduleDraft: vi.fn(),
  friendlyApiError: (error: any, fallback: string) => error?.response?.data?.detail || fallback,
}));

const draft: api.SavedSchedule = {
  version_id: "draft-one", schedule_status: "draft", clinic_name: "Sample Clinic", start_date: "2026-10-19", weeks: 1,
  inputs: {}, requirements: [], staff: [{id: "rn", name: "Sample RN", role: "RN"}],
  assignments: [{date: "2026-10-19", day_name: "Mon", role: "RN", duty: "coverage", staff_id: "rn", notes: [], slot_index: 1, is_bleach: false}],
};
afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listScheduleVersions).mockResolvedValue([]);
});

describe("publishing", () => {
  it("requires explicit review before replacing the published roster", async () => {
    const onLoad = vi.fn(), onPublished = vi.fn();
    vi.mocked(api.publishScheduleVersion).mockResolvedValue({...draft, schedule_status: "published"});
    render(<ScheduleHistory current={draft} revision={0} hasEdits={false} onLoad={onLoad} onPublished={onPublished} />);
    fireEvent.click(screen.getByRole("button", {name: "Publish draft"}));
    expect(api.publishScheduleVersion).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Sample Clinic");
    fireEvent.click(screen.getByRole("button", {name: "Cancel"}));
    expect(api.publishScheduleVersion).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", {name: "Publish draft"}));
    fireEvent.click(screen.getByRole("button", {name: "Confirm publish"}));
    await waitFor(() => expect(onPublished).toHaveBeenCalledOnce());
    expect(api.publishScheduleVersion).toHaveBeenCalledWith("draft-one");
    expect(onLoad).toHaveBeenCalledWith(expect.objectContaining({schedule_status: "published"}));
  });

  it("blocks publishing while assignment edits are unsaved", () => {
    render(<ScheduleHistory current={draft} revision={0} hasEdits={true} onLoad={vi.fn()} onPublished={vi.fn()} />);
    expect((screen.getByRole("button", {name:"Publish draft"}) as HTMLButtonElement).disabled).toBe(true);
  });

  it("allows a previously published version to be reviewed for restoration", () => {
    render(<ScheduleHistory current={{...draft, schedule_status:"published"}} publishedId="newer-version" revision={0} hasEdits={false} onLoad={vi.fn()} onPublished={vi.fn()} />);
    const restore = screen.getByRole("button", {name:"Publish this version"}) as HTMLButtonElement;
    expect(restore.disabled).toBe(false);
    fireEvent.click(restore);
    expect(screen.getByRole("button", {name:"Confirm publish"})).toBeTruthy();
    expect(api.publishScheduleVersion).not.toHaveBeenCalled();
  });
});

it("deletes a draft only after confirmation and clears it from history", async () => {
  const onDeleted = vi.fn();
  vi.mocked(api.deleteScheduleDraft).mockResolvedValue(undefined);
  render(<ScheduleHistory current={draft} revision={0} hasEdits={true} onDeleted={onDeleted} onLoad={vi.fn()} onPublished={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", {name:"Delete draft", exact:true}));
  expect(api.deleteScheduleDraft).not.toHaveBeenCalled();
  expect(screen.getByRole("alert").textContent).toContain("Unsaved assignment edits");
  fireEvent.click(screen.getByRole("button", {name:"Cancel"}));
  expect(api.deleteScheduleDraft).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", {name:"Delete draft", exact:true}));
  fireEvent.click(screen.getByRole("button", {name:"Confirm delete draft"}));
  await waitFor(() => expect(onDeleted).toHaveBeenCalledOnce());
  expect(api.deleteScheduleDraft).toHaveBeenCalledWith("draft-one");
});

it("allows deleting a dropdown draft without opening it first", async () => {
  const onDeleted = vi.fn(), onLoad = vi.fn();
  vi.mocked(api.listScheduleVersions).mockResolvedValue([{id:"selected-draft", state:"draft",
    clinic_name:"Selected Clinic", start_date:"2026-10-19", weeks:"1", created_at:"2026-10-15T12:00:00Z"}]);
  vi.mocked(api.deleteScheduleDraft).mockResolvedValue(undefined);
  render(<ScheduleHistory current={null} revision={0} hasEdits={false} onDeleted={onDeleted} onLoad={onLoad} onPublished={vi.fn()} />);
  await screen.findByRole("option", {name:/Selected Clinic/});
  fireEvent.change(screen.getByRole("combobox", {name:"Saved schedule versions"}), {target:{value:"selected-draft"}});
  fireEvent.click(screen.getByRole("button", {name:"Delete draft", exact:true}));
  expect(screen.getByRole("alert").textContent).toContain("Selected Clinic");
  fireEvent.click(screen.getByRole("button", {name:"Confirm delete draft"}));
  await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("selected-draft"));
  expect(onLoad).not.toHaveBeenCalled();
});

it("protects published versions and preserves the viewed draft on deletion failure", async () => {
  const onDeleted = vi.fn();
  const props = {revision:0, hasEdits:false, onDeleted, onLoad:vi.fn(), onPublished:vi.fn()};
  const {rerender} = render(<ScheduleHistory {...props} current={{...draft, schedule_status:"published"}} />);
  expect((screen.getByRole("button", {name:"Delete draft", exact:true}) as HTMLButtonElement).disabled).toBe(true);
  rerender(<ScheduleHistory {...props} current={draft} />);
  vi.mocked(api.deleteScheduleDraft).mockRejectedValue({response:{data:{detail:"Published schedules cannot be deleted."}}});
  fireEvent.click(screen.getByRole("button", {name:"Delete draft", exact:true}));
  fireEvent.click(screen.getByRole("button", {name:"Confirm delete draft"}));
  await screen.findByText("Published schedules cannot be deleted.");
  expect(onDeleted).not.toHaveBeenCalled();
});

it("keeps assignment edits available after the server rejects a required-rule violation", async () => {
  const onLoad = vi.fn();
  vi.mocked(api.adjustScheduleVersion).mockRejectedValue({response: {data: {detail: "Conflicts with required rest day"}}});
  render(<AssignmentEditor current={draft} onLoad={onLoad} onDirty={vi.fn()} />);
  fireEvent.click(screen.getByRole("checkbox", {name: /Lock 2026-10-19 RN/}));
  fireEvent.click(screen.getByRole("button", {name:"Save adjustments as draft"}));
  await screen.findByText("Conflicts with required rest day");
  expect(onLoad).not.toHaveBeenCalled();
  expect((screen.getByRole("checkbox", {name: /Lock 2026-10-19 RN/}) as HTMLInputElement).checked).toBe(true);
  expect(draft.assignments[0].is_locked).toBeUndefined();
});

it("shows scheduled RN coverage even when only Tech is selected for export", () => {
  const config = {configName:"Sample Clinic", timezone:"America/Chicago", startDate:"2026-10-19", weeks:1,
    patientsPerTech:4, patientsPerRn:12, techsPerRn:4, trials:2, baseSeed:0, usePrevSeed:false,
    scheduledRoles:["Tech","RN"], exportRoles:["Tech"]};
  render(<RunPanel config={config} onConfigChange={vi.fn()} isRunning={false} runResult="" assignments={draft.assignments}
    stats={{rn:1}} displayStaffMap={{rn:"Sample RN"}} hasErrors={false} isAuthed={true} onRun={vi.fn()} onDownloadExcel={vi.fn()} onLoadLatest={vi.fn()} />);
  expect(screen.getByRole("heading", {name:"RN (1)"})).toBeTruthy();
});

it("shows generation failures beside the button and identifies the previous schedule", () => {
  const config = {configName:"Sample Clinic", timezone:"America/Chicago", startDate:"2026-10-19", weeks:1,
    patientsPerTech:4, patientsPerRn:12, techsPerRn:4, trials:2, baseSeed:0, usePrevSeed:false,
    scheduledRoles:["Tech","RN"], exportRoles:["Tech"]};
  const props = {config, onConfigChange:vi.fn(), isRunning:false, runResult:"Old draft result",
    runError:"Choose a valid timezone, such as America/Chicago", assignments:draft.assignments,
    stats:{rn:1}, displayStaffMap:{rn:"Sample RN"}, hasErrors:false, isAuthed:true,
    onRun:vi.fn(), onDownloadExcel:vi.fn(), onLoadLatest:vi.fn()};
  const {rerender} = render(<RunPanel {...props} />);
  expect(screen.getByRole("alert").textContent).toContain("Choose a valid timezone");
  expect(screen.getByRole("alert").textContent).toContain("previously viewed version");
  expect(screen.queryByText("Old draft result")).toBeNull();
  rerender(<RunPanel {...props} isRunning={true} />);
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("Running trials...")).toBeTruthy();
  rerender(<RunPanel {...props} runError="" runResult="Draft generated. Review coverage before publishing." />);
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("Draft generated. Review coverage before publishing.")).toBeTruthy();
});
