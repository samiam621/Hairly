import { useEffect, useRef } from 'react'

const VERDICT_LABELS = {
  safe: 'Looks safe',
  caution: 'Use with caution',
  avoid: 'Avoid',
  unknown: "Can't tell",
}

export default function Result({ result, onScanAnother }) {
  const { product_name, verdict, summary, flagged_ingredients, unrecognized_ingredients, all_ingredients, disclaimer } =
    result
  const headingRef = useRef(null)
  // The form just disappeared, so move focus (and screen readers) to the verdict.
  useEffect(() => headingRef.current.focus(), [])

  return (
    <section>
      <h2 ref={headingRef} tabIndex={-1} className={`verdict ${verdict}`}>
        {VERDICT_LABELS[verdict]}
      </h2>
      {product_name && <p className="product">{product_name}</p>}
      <p>{summary}</p>

      {flagged_ingredients.length > 0 && (
        <ul className="flagged">
          {flagged_ingredients.map((f) => (
            <li key={f.name}>
              <strong>{f.name}</strong> <span className={`severity ${f.severity}`}>{f.severity}</span>
              <br />
              {f.reason}
            </li>
          ))}
        </ul>
      )}

      {unrecognized_ingredients.length > 0 && (
        <details>
          <summary>Ingredients we don't recognize ({unrecognized_ingredients.length})</summary>
          <p>{unrecognized_ingredients.join(', ')}</p>
        </details>
      )}
      {all_ingredients.length > 0 && (
        <details>
          <summary>All ingredients ({all_ingredients.length})</summary>
          <p>{all_ingredients.join(', ')}</p>
        </details>
      )}

      <p className="disclaimer">{disclaimer}</p>
      <button type="button" onClick={onScanAnother}>Scan another product</button>
    </section>
  )
}
