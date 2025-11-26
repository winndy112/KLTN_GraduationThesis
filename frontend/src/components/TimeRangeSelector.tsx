import { useState } from 'react';
import { Select, Group, Stack, Text, Badge } from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { IconClock, IconCalendar } from '@tabler/icons-react';

export interface TimeRangeValue {
    mode: 'preset' | 'custom' | 'realtime';
    presetMinutes?: number;
    fromTime?: Date;
    toTime?: Date;
}

interface TimeRangeSelectorProps {
    value: TimeRangeValue;
    onChange: (value: TimeRangeValue) => void;
}

export default function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
    const [showCustomPickers, setShowCustomPickers] = useState(false);

    const presetOptions = [
        { value: 'realtime', label: 'Real-time (Streaming)' },
        { value: '5', label: 'Last 5 minutes' },
        { value: '10', label: 'Last 10 minutes' },
        { value: '30', label: 'Last 30 minutes' },
        { value: '60', label: 'Last 1 hour' },
        { value: '360', label: 'Last 6 hours' },
        { value: '1440', label: 'Last 24 hours' },
        { value: 'custom', label: 'Custom Range...' },
    ];

    const handleSelectChange = (selectedValue: string | null) => {
        if (!selectedValue) return;

        if (selectedValue === 'realtime') {
            onChange({ mode: 'realtime' });
            setShowCustomPickers(false);
        } else if (selectedValue === 'custom') {
            setShowCustomPickers(true);
            onChange({
                mode: 'custom',
                fromTime: value.fromTime || new Date(Date.now() - 3600000), // Default: 1 hour ago
                toTime: value.toTime || new Date(),
            });
        } else {
            onChange({
                mode: 'preset',
                presetMinutes: parseInt(selectedValue),
            });
            setShowCustomPickers(false);
        }
    };

    const getCurrentSelectValue = () => {
        if (value.mode === 'realtime') return 'realtime';
        if (value.mode === 'custom') return 'custom';
        return value.presetMinutes?.toString() || '60';
    };

    return (
        <Stack gap="xs">
            <Group gap="xs">
                <Select
                    value={getCurrentSelectValue()}
                    onChange={handleSelectChange}
                    data={presetOptions}
                    leftSection={<IconClock size="1rem" />}
                    w={220}
                    placeholder="Select time range"
                />
                {value.mode === 'realtime' && (
                    <Badge color="green" variant="dot" size="lg">
                        Live
                    </Badge>
                )}
            </Group>

            {showCustomPickers && value.mode === 'custom' && (
                <Group gap="xs" align="flex-start">
                    <Stack gap={4}>
                        <Text size="xs" c="dimmed">From</Text>
                        <DateTimePicker
                            value={value.fromTime || null}
                            onChange={(dateValue) => {
                                if (dateValue) {
                                    const date = typeof dateValue === 'string' ? new Date(dateValue) : dateValue;
                                    onChange({
                                        ...value,
                                        fromTime: date,
                                    });
                                }
                            }}
                            placeholder="Pick start date and time"
                            leftSection={<IconCalendar size="1rem" />}
                            valueFormat="DD/MM/YYYY HH:mm:ss"
                            maxDate={value.toTime || new Date()}
                            clearable
                        />
                    </Stack>
                    <Stack gap={4}>
                        <Text size="xs" c="dimmed">To</Text>
                        <DateTimePicker
                            value={value.toTime || null}
                            onChange={(dateValue) => {
                                if (dateValue) {
                                    const date = typeof dateValue === 'string' ? new Date(dateValue) : dateValue;
                                    onChange({
                                        ...value,
                                        toTime: date,
                                    });
                                }
                            }}
                            placeholder="Pick end date and time"
                            leftSection={<IconCalendar size="1rem" />}
                            valueFormat="DD/MM/YYYY HH:mm:ss"
                            minDate={value.fromTime}
                            maxDate={new Date()}
                            clearable
                        />
                    </Stack>
                </Group>
            )}
        </Stack>
    );
}
