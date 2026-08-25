import { useMemo, useState, type ReactElement } from "react";
import type { RouteEnvelope, SentenceClaim } from "@redtrip/contracts";
import { shortRecordId } from "./sourceLabels";

const SENT_SPLIT = /(?<=[。！？；])/;

/** 取某站点、某叙事块（story_card）的句子级溯源标注。 */
export function findStopClaims(
  envelope: RouteEnvelope,
  stopOrder: number,
  sourceBlock: "story_card" | "route_card" = "story_card",
): SentenceClaim[] {
  const sp = envelope.sentence_provenance;
  if (!sp?.per_stop) return [];
  const entry = sp.per_stop.find(
    (p) => p.stop_index === stopOrder && p.source_block === sourceBlock,
  );
  return entry?.sentences ?? [];
}

function findByContainment(
  sent: string,
  claims: SentenceClaim[],
): SentenceClaim | undefined {
  for (const c of claims) {
    const t = c.text.trim();
    if (!t) continue;
    if (sent.includes(t) || t.includes(sent)) return c;
  }
  return undefined;
}

function ProvenancePopover({
  claim,
  numByUri,
  onClose,
}: {
  claim: SentenceClaim;
  numByUri: Map<string, number>;
  onClose: () => void;
}) {
  return (
    <span className="prov-popover" role="dialog" aria-label="本句溯源">
      <button
        type="button"
        className="prov-popover-close"
        aria-label="关闭"
        onClick={onClose}
      >
        ×
      </button>
      <span className="prov-popover-title">本句可溯源至</span>
      <ul className="prov-fact-list">
        {claim.fact_uris.map((u, i) => (
          <li key={u} className="prov-fact-item">
            <sup className="prov-fact-num">{numByUri.get(u) ?? i + 1}</sup>
            <span className="prov-fact-label">
              {claim.fact_labels[i] ?? "馆藏事实"}
            </span>
            <code className="prov-record" title={u}>
              {shortRecordId(u)}
            </code>
            {u.startsWith("http") && (
              <a
                className="prov-link"
                href={u}
                target="_blank"
                rel="noreferrer"
              >
                原记录
              </a>
            )}
          </li>
        ))}
      </ul>
    </span>
  );
}

/** 把叙事正文按段落、句子拆分，并在事实句句末渲染可点击的溯源标记。 */
export function ProvenanceBody({
  body,
  claims,
}: {
  body: string;
  claims: SentenceClaim[];
}) {
  const byText = useMemo(() => {
    const m = new Map<string, SentenceClaim>();
    for (const c of claims) {
      const t = c.text.trim();
      if (t && !m.has(t)) m.set(t, c);
    }
    return m;
  }, [claims]);

  const numByUri = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of claims) {
      for (const u of c.fact_uris) {
        if (!m.has(u)) m.set(u, m.size + 1);
      }
    }
    return m;
  }, [claims]);

  const [openKey, setOpenKey] = useState<string | null>(null);

  const paragraphs = body.split("\n\n");
  const out: ReactElement[] = [];

  paragraphs.forEach((para, pi) => {
    const sentences = para
      .split(SENT_SPLIT)
      .map((s) => s.trim())
      .filter(Boolean);
    const paraEls: ReactElement[] = [];

    sentences.forEach((sent, si) => {
      const claim = byText.get(sent) ?? findByContainment(sent, claims);
      paraEls.push(
        <span key={`s${si}`} className="prov-sentence">
          {sent}
        </span>,
      );
      if (claim && claim.fact_uris.length > 0) {
        const key = `${pi}-${si}`;
        const nums = claim.fact_uris
          .map((u) => numByUri.get(u))
          .filter((n): n is number => typeof n === "number");
        paraEls.push(
          <span className="prov-wrap" key={`w${si}`}>
            <button
              type="button"
              className="prov-marker"
              aria-label="查看本句出处"
              aria-expanded={openKey === key}
              onClick={() => setOpenKey(openKey === key ? null : key)}
            >
              {nums.map((n) => (
                <sup key={n}>{n}</sup>
              ))}
            </button>
            {openKey === key && (
              <ProvenancePopover
                claim={claim}
                numByUri={numByUri}
                onClose={() => setOpenKey(null)}
              />
            )}
          </span>,
        );
      }
    });

    out.push(
      <p className="body" key={`p${pi}`}>
        {paraEls}
      </p>,
    );
  });

  if (out.length === 0) {
    return <p className="body">{body}</p>;
  }
  return <>{out}</>;
}
