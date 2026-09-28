//Hairly endpoint functions

import { request } from './client'

export const analyzeBarcode = (barcode, concern) =>
  request('/api/analyze/barcode', { method: 'POST', body: { barcode, concern } })