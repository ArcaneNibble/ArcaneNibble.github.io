def ascii_to_entity(i):
    CODES = [
        ('NUL', 'Null'),
        ('SOH', 'Start of Heading'),
        ('STX', 'Start of Text'),
        ('ETX', 'End of Text'),
        ('EOT', 'End of Transmission'),
        ('ENQ', 'Enquiry'),
        ('ACK', 'Acknowledge'),
        ('BEL', 'Bell'),

        ('BS', 'Backspace'),
        ('HT', 'Horizontal Tabulation'),
        ('LF', 'Line Feed'),
        ('VT', 'Vertical Tabulation'),
        ('FF', 'Form Feed'),
        ('CR', 'Carriage Return'),
        ('SO', 'Shift Out'),
        ('SI', 'Shift In'),


        ('DLE', 'Data Link Escape'),
        ('DC1', 'Device Control One'),
        ('DC2', 'Device Control Two'),
        ('DC3', 'Device Control Three'),
        ('DC4', 'Device Control Four'),
        ('NAK', 'Negative Acknowledge'),
        ('SYN', 'Synchronous Idle'),
        ('ETB', 'End of Transmission Block'),

        ('CAN', 'Cancel'),
        ('EM', 'End of medium'),
        ('SUB', 'Substitute'),
        ('ESC', 'Escape'),
        ('FS', 'File Separator'),
        ('GS', 'Group Separator'),
        ('RS', 'Record Separator'),
        ('US', 'Unit Separator'),
    
        ('SP', 'Space'),
    ]
    if i <= 0x20:
        return f'<td class="smallcaps"><span title="{CODES[i][1]}">{CODES[i][0]}</span></td>'
    elif i == 0x7f:
        return '<td class="smallcaps"><span title="Delete">DEL</span></td>'
    else:
        return '<td>&#{:d};</td>'.format(i)

def cp1252_to_entity(i):
    try:
        unicode = ord(bytes([i]).decode('windows-1252'))
        return f'<td><span title="U+{unicode:04x}">&#{unicode:d};</span></td>'
    except UnicodeError:
        return '<td class="err"></td>'

def cp437_to_entity(i):
    try:
        unicode = ord(bytes([i]).decode('cp437'))
        return f'<td><span title="U+{unicode:04x}">&#{unicode:d};</span></td>'
    except UnicodeError:
        return '<td class="err"></td>'
