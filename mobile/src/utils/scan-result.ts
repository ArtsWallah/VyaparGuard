export type ScanResult = {
  schema_version?: string;
  scan_id: string;
  status: 'VERIFIED' | 'SUSPICIOUS' | 'UNVERIFIED';
  extracted: {
    amount: number | null;
    transaction_id: string | null;
    date: string | null;
    upi_reference?: string | null;
    reference?: string | null;
    time?: string | null;
    timestamp?: string | null;
    payee?: string | null;
    currency?: string | null;
    displayed_status?: string | null;
  };
  checks: {
    duplicate: boolean;
    trusted_record_match: boolean;
  };
  reasons: string[];
  verification_source: string;
  file?: {
    format?: string;
    width?: number;
    height?: number;
    size_bytes?: number;
    sha256?: string;
    filename?: string | null;
    declared_content_type?: string | null;
  };
  ocr?: {
    raw_text?: string;
    confidence?: number | null;
    amount?: number | null;
    currency?: string | null;
    date?: string | null;
    time?: string | null;
    timestamp?: string | null;
    transaction_id?: string | null;
    upi_reference?: string | null;
    reference?: string | null;
    payee?: string | null;
    displayed_status?: string | null;
    fields_missing?: string[];
  };
  image_quality?: {
    width?: number;
    height?: number;
    sharpness_score?: number | null;
  };
  forensics?: {
    ela_mean?: number | null;
    indicators?: string[];
    assessment?: string;
    limitations?: string[];
  };
  errors?: string[];
  verification?: {
    status?: 'VERIFIED' | 'SUSPICIOUS' | 'UNVERIFIED';
    source?: string;
    reason?: string;
  };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === 'string';
}

function isOptionalNumber(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    (typeof value === 'number' && Number.isFinite(value))
  );
}

function isStringArray(value: unknown): boolean {
  return Array.isArray(value) && value.every((item: unknown) => typeof item === 'string');
}

export function isScanResult(value: unknown): value is ScanResult {
  if (!isRecord(value) || !isRecord(value.extracted) || !isRecord(value.checks)) {
    return false;
  }

  const { extracted, checks } = value;

  const validCore = (
    typeof value.scan_id === 'string' &&
    (value.status === 'VERIFIED' ||
      value.status === 'SUSPICIOUS' ||
      value.status === 'UNVERIFIED') &&
    (extracted.amount === null ||
      (typeof extracted.amount === 'number' && Number.isFinite(extracted.amount))) &&
    (extracted.transaction_id === null ||
      typeof extracted.transaction_id === 'string') &&
    (extracted.date === null || typeof extracted.date === 'string') &&
    typeof checks.duplicate === 'boolean' &&
    typeof checks.trusted_record_match === 'boolean' &&
    isStringArray(value.reasons) &&
    typeof value.verification_source === 'string'
  );

  if (!validCore) return false;

  const extractedStrings = [
    extracted.upi_reference,
    extracted.reference,
    extracted.time,
    extracted.timestamp,
    extracted.payee,
    extracted.currency,
    extracted.displayed_status,
  ];

  if (!extractedStrings.every(isOptionalString)) return false;
  if (value.schema_version !== undefined && typeof value.schema_version !== 'string') return false;

  if (value.file !== undefined) {
    if (!isRecord(value.file)) return false;
    if (
      !isOptionalString(value.file.format) ||
      !isOptionalNumber(value.file.width) ||
      !isOptionalNumber(value.file.height) ||
      !isOptionalNumber(value.file.size_bytes) ||
      !isOptionalString(value.file.sha256) ||
      !isOptionalString(value.file.filename) ||
      !isOptionalString(value.file.declared_content_type)
    ) {
      return false;
    }
  }

  if (value.ocr !== undefined) {
    if (!isRecord(value.ocr)) return false;
    const ocr = value.ocr;
    if (
      !isOptionalString(ocr.raw_text) ||
      !isOptionalNumber(ocr.confidence) ||
      !isOptionalNumber(ocr.amount) ||
      !isOptionalString(ocr.currency) ||
      !isOptionalString(ocr.date) ||
      !isOptionalString(ocr.time) ||
      !isOptionalString(ocr.timestamp) ||
      !isOptionalString(ocr.transaction_id) ||
      !isOptionalString(ocr.upi_reference) ||
      !isOptionalString(ocr.reference) ||
      !isOptionalString(ocr.payee) ||
      !isOptionalString(ocr.displayed_status) ||
      (ocr.fields_missing !== undefined && !isStringArray(ocr.fields_missing))
    ) {
      return false;
    }
  }

  if (value.image_quality !== undefined) {
    if (!isRecord(value.image_quality)) return false;
    if (
      !isOptionalNumber(value.image_quality.width) ||
      !isOptionalNumber(value.image_quality.height) ||
      !isOptionalNumber(value.image_quality.sharpness_score)
    ) {
      return false;
    }
  }

  if (value.forensics !== undefined) {
    if (!isRecord(value.forensics)) return false;
    if (
      !isOptionalNumber(value.forensics.ela_mean) ||
      !isOptionalString(value.forensics.assessment) ||
      (value.forensics.indicators !== undefined && !isStringArray(value.forensics.indicators)) ||
      (value.forensics.limitations !== undefined && !isStringArray(value.forensics.limitations))
    ) {
      return false;
    }
  }

  if (value.errors !== undefined && !isStringArray(value.errors)) return false;

  if (value.verification !== undefined) {
    if (!isRecord(value.verification)) return false;
    const verificationStatus = value.verification.status;
    if (
      (verificationStatus !== undefined &&
        verificationStatus !== 'VERIFIED' &&
        verificationStatus !== 'SUSPICIOUS' &&
        verificationStatus !== 'UNVERIFIED') ||
      !isOptionalString(value.verification.source) ||
      !isOptionalString(value.verification.reason)
    ) {
      return false;
    }
  }

  return true;
}