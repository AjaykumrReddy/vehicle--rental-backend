# Photo Storage & Privacy Policy

## Dual Storage Strategy

### **Why Store Both Versions?**

✅ **LEGAL** - Here's why it's necessary:

1. **Verification & Trust**
   - Platform needs to verify vehicle authenticity
   - Insurance claims require original photos
   - Dispute resolution needs unaltered evidence

2. **User Experience**
   - Renters need clear photos after booking
   - Owners want to show vehicle condition accurately
   - Reduces post-booking disputes

3. **Legal Compliance**
   - GDPR allows storage with "legitimate interest"
   - Terms of Service must disclose this practice
   - Users consent during registration

## Storage Architecture

```
vehicle-photos/              (Public bucket - Blurred)
├── vehicles/
│   └── {vehicle_id}/
│       └── blurred_{uuid}.jpg

vehicle-photos-private/      (Private bucket - Original)
├── vehicles/
│   └── {vehicle_id}/
│       └── original_{uuid}.jpg
```

## Access Control Matrix

| User Type | Blurred Photos | Original Photos |
|-----------|---------------|-----------------|
| Public/Guest | ✅ Yes | ❌ No |
| Registered User | ✅ Yes | ❌ No |
| Vehicle Owner | ✅ Yes | ✅ Yes (Always) |
| Pending Booking | ✅ Yes | ❌ No |
| Confirmed Booking | ✅ Yes | ✅ Yes |
| Active Rental | ✅ Yes | ✅ Yes |
| Completed Rental | ✅ Yes | ✅ Yes (30 days) |
| Platform Admin | ✅ Yes | ✅ Yes (Audit only) |

## Real-World Examples

### **Turo**
- Stores both versions
- Shows blurred in listings
- Reveals original 24h before trip
- Keeps for insurance purposes

### **Getaround**
- AI-blurred public photos
- Original shared at booking
- Stored for 2 years (legal requirement)

### **Airbnb**
- Stores original property photos
- Hides exact address until booking
- Similar privacy-by-design approach

## Legal Requirements

### **GDPR Compliance**
```
Article 6(1)(f) - Legitimate Interest:
"Processing is necessary for legitimate interests pursued 
by the controller, except where such interests are overridden 
by the interests or fundamental rights of the data subject."
```

**Our Legitimate Interests:**
- Fraud prevention
- Insurance claims
- Dispute resolution
- Platform safety

### **User Consent**
Terms of Service must include:
```
"By uploading photos, you consent to:
1. Storage of original and processed versions
2. Public display of privacy-protected versions
3. Sharing originals with confirmed renters
4. Retention for legal/insurance purposes"
```

## Data Retention Policy

| Photo Type | Retention Period | Reason |
|------------|------------------|--------|
| Blurred | Until vehicle deleted | Public listing |
| Original | 2 years after last booking | Legal/Insurance |
| Deleted Vehicle | 90 days | Grace period |
| Disputed Booking | 5 years | Legal requirement |

## Security Measures

1. **Storage Separation**
   - Public bucket: Blurred photos only
   - Private bucket: Restricted access, signed URLs

2. **Access Logging**
   - Log all original photo access
   - Alert on suspicious patterns
   - Audit trail for compliance

3. **Encryption**
   - At rest: AES-256
   - In transit: TLS 1.3
   - Signed URLs: Time-limited (1 hour)

4. **Access Control**
   - Role-based permissions
   - Booking status verification
   - Owner verification

## API Endpoints

```
GET /vehicles/{id}                    → Returns blurred photos
GET /vehicle-photos/{id}/original     → Returns original (authorized only)
POST /vehicles/{id}/upload_photos     → Stores both versions
```

## Implementation Checklist

- [x] Store both blurred and original versions
- [x] Separate storage buckets (public/private)
- [x] Access control based on booking status
- [x] Audit logging for original photo access
- [ ] Terms of Service disclosure
- [ ] Privacy Policy update
- [ ] User consent flow
- [ ] Data retention automation
- [ ] GDPR data export (include both versions)
- [ ] Right to deletion workflow

## Cost Considerations

**Storage Costs:**
- Blurred: ~500KB per photo
- Original: ~2MB per photo
- Total: ~2.5MB per photo
- 1000 vehicles × 5 photos = 12.5GB
- AWS S3: ~$0.30/month

**Worth it for:**
- Legal protection
- User trust
- Dispute resolution
- Insurance compliance

## Conclusion

Storing both versions is:
- ✅ **Legal** (with proper disclosure)
- ✅ **Necessary** (for business operations)
- ✅ **Industry Standard** (Turo, Getaround do it)
- ✅ **Cost-effective** (minimal storage cost)
- ✅ **User-friendly** (better experience post-booking)

**Key**: Transparency + Access Control + Legitimate Purpose = Legal Compliance
