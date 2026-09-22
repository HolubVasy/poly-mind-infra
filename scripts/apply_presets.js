// Makes the owner's presets in MongoDB equal to presets/presets.json.
// Run by apply.sh inside the chat-mongodb container:
//   mongosh --quiet LibreChat /tmp/apply_presets.js
// Environment: DRY_RUN=1 reports only; BACKUP_TAG names the backup collection.
//
// Presets are matched by presetId, so renaming a preset (for example when its
// price marker changes) updates it in place instead of creating a duplicate.
// `order` is what LibreChat sorts the preset menu by (api/models/Preset.js:
// ascending order, missing = 10000, then newest first); build_presets.py
// assigns it, so the menu order is decided in slots.yaml, not by Mongo.
// Presets in the database that are not in the file are deleted - the file is
// the whole truth. Before any write the current presets are copied to the
// collection presets_backup_<BACKUP_TAG>.
const fs = require("fs");

const dry = process.env.DRY_RUN === "1";
const tag = process.env.BACKUP_TAG || new Date().toISOString().replace(/[-:.]/g, "");
const wanted = JSON.parse(fs.readFileSync("/tmp/presets.json", "utf8")).presets;

// Presets belong to the owner's account, the only ADMIN. The mother uses the
// same account, so these are her presets too.
const admin = db.users.findOne({ role: "ADMIN" });
if (!admin) {
  print("[presets] ERROR: no ADMIN user");
  quit(1);
}
const owner = String(admin._id);

const FIELDS = ["title", "endpoint", "endpointType", "model", "maxContextTokens", "resendFiles", "web_search", "tags", "isArchived", "order"];
const current = db.presets.find({ user: owner }).toArray();
const byId = Object.fromEntries(current.map((p) => [p.presetId, p]));
const wantedIds = new Set(wanted.map((p) => p.presetId));

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const toInsert = [];
const toUpdate = [];
for (const w of wanted) {
  const have = byId[w.presetId];
  if (!have) {
    toInsert.push(w);
    continue;
  }
  const diff = FIELDS.filter((f) => !same(have[f], w[f]));
  if (diff.length) toUpdate.push({ w, diff, have });
}
const toDelete = current.filter((p) => !wantedIds.has(p.presetId));

for (const w of toInsert) print(`[presets] add     ${w.title} -> ${w.model}`);
for (const u of toUpdate) print(`[presets] update  ${u.have.title}: ${u.diff.map((f) => `${f} ${JSON.stringify(u.have[f])} -> ${JSON.stringify(u.w[f])}`).join("; ")}`);
for (const d of toDelete) print(`[presets] delete  ${d.title} (${d.model})`);

if (!toInsert.length && !toUpdate.length && !toDelete.length) {
  print(`[presets] no changes (${current.length} presets)`);
  quit(0);
}
if (dry) {
  print("[presets] dry run, nothing written");
  quit(0);
}

const backupName = `presets_backup_${tag}`;
if (current.length) db.getCollection(backupName).insertMany(current);
print(`[presets] backup: ${current.length} preset(s) -> ${backupName}`);

const now = new Date();
for (const w of toInsert) {
  const doc = { user: owner, presetId: w.presetId, createdAt: now, updatedAt: now };
  for (const f of FIELDS) if (w[f] !== undefined) doc[f] = w[f];
  db.presets.insertOne(doc);
}
for (const { w } of toUpdate) {
  const set = { updatedAt: now };
  const unset = {};
  for (const f of FIELDS) {
    if (w[f] === undefined) unset[f] = "";
    else set[f] = w[f];
  }
  const upd = { $set: set };
  if (Object.keys(unset).length) upd.$unset = unset;
  db.presets.updateOne({ user: owner, presetId: w.presetId }, upd);
}
if (toDelete.length) db.presets.deleteMany({ user: owner, presetId: { $in: toDelete.map((d) => d.presetId) } });
print(`[presets] applied: +${toInsert.length} ~${toUpdate.length} -${toDelete.length}, now ${db.presets.countDocuments({ user: owner })}`);
