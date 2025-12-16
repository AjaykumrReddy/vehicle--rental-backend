# Privacy & Security Guidelines - RediRental

## License Plate Protection

### Why We Blur License Plates

1. **Legal Compliance**
   - GDPR Article 4(1): License plates are Personal Identifiable Information (PII)
   - CCPA requirements for California users
   - Local data protection laws

2. **Security Risks**
   - Vehicle tracking and stalking
   - License plate cloning/fraud
   - Identity theft
   - Unauthorized surveillance

3. **Platform Liability**
   - You're responsible for protecting user data
   - Potential lawsuits from privacy violations
   - Regulatory fines (GDPR: up to €20M or 4% revenue)

### Implementation Strategy

**Automatic Blurring:**
- All uploaded photos are processed to detect and blur license plates
- Uses OpenCV computer vision for detection
- Applied before storage (can't be reversed)

**When to Show Unblurred:**
- ONLY after booking is confirmed
- Owner can share unblurred photo directly via messaging
- Never store unblurred versions in public listings

### Real-World Examples

**Turo:**
- Blurs plates in all listing photos
- Shows actual plate only after booking confirmed
- Owner manually shares via in-app messaging

**Getaround:**
- Automatic plate detection and blurring
- Reveals plate 24 hours before trip starts
- Stored separately from listing photos

**Uber/Lyft:**
- Shows only last 3 digits of plate
- Full plate visible only to matched rider
- Time-limited visibility

## Additional Privacy Measures

### Owner Information
- Hide exact address until booking confirmed
- Show only approximate location (500m radius)
- Phone numbers masked until booking

### Renter Information
- Profile photos optional
- Full name shown only after booking
- Contact info shared only between matched parties

### Data Retention
- Delete unconfirmed bookings after 30 days
- Anonymize data after 2 years
- Right to deletion (GDPR Article 17)

## Best Practices

1. **Minimize Data Collection**: Only collect what's necessary
2. **Encrypt Sensitive Data**: Use encryption at rest and in transit
3. **Access Controls**: Limit who can see PII
4. **Audit Logs**: Track all access to sensitive data
5. **User Consent**: Clear opt-ins for data usage
6. **Data Portability**: Allow users to export their data
7. **Breach Notification**: 72-hour notification requirement (GDPR)

## Technical Implementation

```python
# Before upload
blurred_image = blur_license_plate(original_image)
upload_to_storage(blurred_image)

# After booking confirmed
send_message_with_attachment(original_image, conversation_id)
```

## Compliance Checklist

- [x] License plates blurred in public listings
- [x] Exact addresses hidden until booking
- [x] Phone numbers masked
- [x] Soft delete with retention policy
- [ ] GDPR consent forms
- [ ] Privacy policy page
- [ ] Terms of service
- [ ] Data export functionality
- [ ] Account deletion workflow
- [ ] Cookie consent banner
