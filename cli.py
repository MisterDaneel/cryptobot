import urwid

def pos_neg_change(change):
    if not change:
        return "0"
    else:
        return ("+{}".format(change) if change >= 0 else str(change))


def get_color(change):
    color = 'change '
    if change < 0:
        color += 'negative'
    return color


def get_order_color(status):
    if status == 'DONE':
        return 'change '
    elif status == 'FAILED':
        return 'change negative'
    else:
        return 'white'


def get_update(result):
    # first header
    updates = [
        ('headers', u'Coin \t| '.expandtabs(15)),
        ('headers', u'Last Price \t| '.expandtabs(15)),
        ('headers', u'Gain \t| '.expandtabs(15)),
        ('headers', u'% Gain\n'.expandtabs(15))
    ]

    # coin
    updates.append((
        'white',
        '{} \t| '.format(result['coin']).expandtabs(15)
    ))
    # last price
    updates.append((
        'white',
        '{}$ \t| '.format(result['price']).expandtabs(15)
    ))
    # gain %
    updates.append((
        get_color(result['gain']),
        '{}% \t'.format(pos_neg_change(float(result['%']))).expandtabs(15)
    ))
    updates.append((
        'white',
        '| '
    ))
    # gain
    updates.append((
        get_color(result['gain']),
        '{}$ \t '.format(pos_neg_change(result['gain'])).expandtabs(15)
    ))
    updates.append((
        'white',
        '\n\n\n'
    ))
    # ENTRY
    updates.append((
        'headers',
        u'ENTRY '
    ))
    updates.append((
        get_order_color(result['entry']['status']),
        '{}\t'.format(
            result['entry']['status'],
        ).expandtabs(3)
    ))
    updates.append((
        'white',
        '{}$; Quantity {}; Wager {}$\n'.format(
            result['entry']['price'],
            result['entry']['quantity'],
            result['entry']['wager'],
        ).expandtabs(4)
    ))

    # TPX
    for tp in sorted(result['TPS']):
        updates.append((
            'headers',
            u'{}   '.format(tp)
        ))
        updates.append((
            get_order_color(result['TPS'][tp]['status']),
            '{}\t'.format(
                result['TPS'][tp]['status'],
            ).expandtabs(3)
        ))
        updates.append((
            'white',
    '{}$; Quantity {}; Total {:.2f}$ (Profit: {}$)\n'.format(
                result['TPS'][tp]['price'],
                result['TPS'][tp]['quantity'],
                result['TPS'][tp]['quantity'] * result['TPS'][tp]['price'],
                '{:.2f}'.format((result['TPS'][tp]['price'] - result['entry']['price']) * result['TPS'][tp]['quantity']),
            ).expandtabs(4)
        ))



    return updates


def update(results):
    #print(results)
    result = get_update(results)
    #with open('test.txt', 'a') as testfile:
    #    testfile.write(str(result)+'\n')
    #print(result)
    quote_box.base_widget.set_text(result)
    main_loop.draw_screen()


# Handle key presses
def handle_input(key):
    #if key == 'R' or key == 'r':
    #    refresh(main_loop, '')

    if key == 'Q' or key == 'q':
        raise urwid.ExitMainLoop()

# Set up color scheme
palette = [
    ('titlebar', 'dark red', ''),
    ('refresh button', 'dark green,bold', ''),
    ('quit button', 'dark red', ''),
    ('getting quote', 'dark blue', ''),
    ('headers', 'white,bold', ''),
    ('change ', 'dark green', ''),
    ('change negative', 'dark red', '')]

header_text = urwid.Text(u' CRYPTO')
header = urwid.AttrMap(header_text, 'titlebar')

# Create the menu
menu = urwid.Text([
    #u'Press (', ('refresh button', u'r'), u') to manually refresh. ',
    u'Press (', ('quit button', u'q'), u') to quit.'
])

# Create the quotes box
quote_text = urwid.Text(u'Waiting for data !')
quote_filler = urwid.Filler(
    quote_text,
    valign='top',
    top=1,
    bottom=1
)
v_padding = urwid.Padding(quote_filler, left=1, right=1)
quote_box = urwid.LineBox(v_padding)

# Assemble the widgets
layout = urwid.Frame(
    header=header,
    body=quote_box,
    footer=menu
)

main_loop = urwid.MainLoop(
    layout,
    palette,
    unhandled_input=handle_input
)

def run_cli():
    main_loop.run()
    None
