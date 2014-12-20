from collections import namedtuple
from django.contrib.humanize.templatetags.humanize import intcomma

from django import template

from psutil import AccessDenied


cpuTuple = namedtuple('cpuTuple',
                      'core, used')

memTuple = namedtuple('memTuple',
                      'total, used')

diskPartTuple = namedtuple('diskPartTuple',
                           'device, mountpoint, fstype, total, percent')

networkTuple = namedtuple('networkTuple',
                          'device, sent, recv, pkg_sent, pkg_recv')

processTuple = namedtuple('processTuple',
                          'pid, name, status, user, memory')


def bytes2human(num):
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')


register = template.Library()


def tofloat(value):
    try:
        return float(value)
    except ValueError:
        return 0


register.filter(name='tofloat', filter_func=tofloat)


class SysMon(template.Node):
    def render(self, context):
        try:
            import psutil as pu
        except:
            context['error_psutil'] = 'not_found'
            return ''

        # cpu
        cpu_info = cpuTuple(
            core=pu.NUM_CPUS,
            used=intcomma(pu.cpu_percent(), use_l10n=False))

        # memory
        mem_info = memTuple(
            total=bytes2human(pu.TOTAL_PHYMEM),
            used=intcomma(pu.virtual_memory().percent, use_l10n=False))

        # disk
        partitions = list()
        for part in pu.disk_partitions():
            try:
                disk_usage_total = bytes2human(pu.disk_usage(part.mountpoint).total)
                usage_percentage = intcomma(pu.disk_usage(part.mountpoint).percent,
                                            use_l10n=False)
            except:
                disk_usage_total = "n/a"
                usage_percentage = "n/a"
            partitions.append(
                diskPartTuple(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total=disk_usage_total,
                    percent=usage_percentage
                )
            )

        # network
        networks = list()
        for k, v in pu.net_io_counters(pernic=True).items():
            # Skip loopback interface
            if k == 'lo':
                continue

            networks.append(
                networkTuple(
                    device=k,
                    sent=bytes2human(v.bytes_sent),
                    recv=bytes2human(v.bytes_recv),
                    pkg_sent=v.packets_sent,
                    pkg_recv=v.packets_recv))

        # processes
        processes = list()
        for process in pu.process_iter():

            try:
                percent = process.get_memory_percent()
                process_name = process.name()
                process_username = process.username()
            except AccessDenied:
                percent = "Access Denied"
                process_name = "Access Denied"
                process_username = "Access Denied"
            else:
                percent = int(percent)
                #process_name = "Access Denied"
                #process_username = "Access Denied"

            processes.append(processTuple(
                pid=process.pid,
                name=process_name,
                status=process.status,
                user=process_username,
                memory=percent))

        processes_sorted = sorted(
            processes, key=lambda p: p.memory, reverse=True)

        all_stats = {
            'cpu_info': cpu_info,
            'mem_info': mem_info,
            'partitions': partitions,
            'networks': networks,
            'processes': processes_sorted[:10],
        }

        context.update(all_stats)

        return ''


@register.tag
def get_system_stats(parser, token):
    return SysMon()
