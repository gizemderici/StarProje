class SetThermostatSetpoints < OpenStudio::Measure::ModelMeasure
  def name
    'Set Thermostat Setpoints'
  end

  def description
    'Applies constant heating and cooling setpoints to every thermostat in the model.'
  end

  def modeler_description
    'Replaces the schedules on each OS:ThermostatSetpoint:DualSetpoint with constant ' \
      'schedules, so the dead band is defined solely by the two arguments.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    heating = OpenStudio::Measure::OSArgument.makeDoubleArgument('heating_setpoint_c', true)
    heating.setDisplayName('Heating setpoint (C)')
    heating.setDefaultValue(22.0)
    args << heating

    cooling = OpenStudio::Measure::OSArgument.makeDoubleArgument('cooling_setpoint_c', true)
    cooling.setDisplayName('Cooling setpoint (C)')
    cooling.setDefaultValue(24.0)
    args << cooling

    args
  end

  # Olu bandin altina inilmesi EnergyPlus'ta isitma ve sogutmanin ayni anda
  # calismasina yol acar; en az bu kadar fark sart kosulur.
  MINIMUM_DEAD_BAND_K = 0.5

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    heating = runner.getDoubleArgumentValue('heating_setpoint_c', user_arguments)
    cooling = runner.getDoubleArgumentValue('cooling_setpoint_c', user_arguments)

    if cooling - heating < MINIMUM_DEAD_BAND_K
      runner.registerError(
        "Cooling setpoint (#{cooling} C) must exceed heating setpoint (#{heating} C) " \
          "by at least #{MINIMUM_DEAD_BAND_K} K."
      )
      return false
    end

    thermostats = model.getThermostatSetpointDualSetpoints
    if thermostats.empty?
      runner.registerError('No OS:ThermostatSetpoint:DualSetpoint objects found.')
      return false
    end

    heating_schedule = OpenStudio::Model::ScheduleConstant.new(model)
    heating_schedule.setName(format('heating setpoint %.1f C', heating))
    heating_schedule.setValue(heating)

    cooling_schedule = OpenStudio::Model::ScheduleConstant.new(model)
    cooling_schedule.setName(format('cooling setpoint %.1f C', cooling))
    cooling_schedule.setValue(cooling)

    thermostats.each do |thermostat|
      thermostat.setHeatingSetpointTemperatureSchedule(heating_schedule)
      thermostat.setCoolingSetpointTemperatureSchedule(cooling_schedule)
    end

    runner.registerInitialCondition("#{thermostats.length} thermostat(s) found.")
    runner.registerValue('heating_setpoint_c', heating, 'C')
    runner.registerValue('cooling_setpoint_c', cooling, 'C')
    runner.registerValue('dead_band_k', cooling - heating, 'K')
    runner.registerFinalCondition(
      "Set #{heating} / #{cooling} C on #{thermostats.length} thermostat(s); " \
        "dead band #{(cooling - heating).round(2)} K."
    )
    true
  rescue StandardError => e
    runner.registerError("Set Thermostat Setpoints failed: #{e.message}")
    false
  end
end

SetThermostatSetpoints.new.registerWithApplication
