import assert from "node:assert/strict";
import test from "node:test";
import { PythonWorker } from "../python-worker.js";

const echoScript = `
const readline=require('node:readline').createInterface({input:process.stdin});
readline.on('line', line => {
  const request=JSON.parse(line);
  process.stdout.write(JSON.stringify({requestId:request.requestId,result:{status:'ok'}})+'\\n');
});`;

test("correlates concurrent JSONL responses", async () => {
  const worker = new PythonWorker(process.execPath, ["-e", echoScript], 1000);
  try {
    const [first, second] = await Promise.all([worker.call("a", {}), worker.call("b", {})]);
    assert.equal(first.result.status, "ok");
    assert.equal(second.result.status, "ok");
  } finally { worker.close(); }
});

test("rejects pending request when child exits", async () => {
  const worker = new PythonWorker(process.execPath, ["-e", "process.stdin.once('data',()=>process.exit(2))"], 1000);
  await assert.rejects(worker.call("a", {}), /exited/);
  worker.close();
});

test("times out and clears a request", async () => {
  const worker = new PythonWorker(process.execPath, ["-e", "process.stdin.resume();setInterval(()=>{},1000)"], 30);
  await assert.rejects(worker.call("a", {}), /timeout/);
  worker.close();
});
