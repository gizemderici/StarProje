class SetElevatorLoad < OpenStudio::Measure::ModelMeasure
  def name
    'Set Elevator Load'
  end

  def description
    'Sets the connected power of the elevator motor equipment definition.'
  end

  def modeler_description
    'The definition is matched by a name pattern and its design level is set to an ' \
      'absolute value, so the measure is idempotent and independent of run order. ' \
      'The seed model carries 5000 W, which is a peak rating rather than a verified ' \
      'continuous load; see docs/baseline_assumptions.md.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    power = OpenStudio::Measure::OSArgument.makeDoubleArgument('elevator_power_w', true)
    power.setDisplayName('Elevator motor connected power (W)')
    power.setDefaultValue(5000.0)
    args << power

    pattern = OpenStudio::Measure::OSArgument.makeStringArgument('definition_name_pattern', true)
    pattern.setDisplayName('Name pattern identifying the elevator definition')
    pattern.setDefaultValue('asansor')
    args << pattern

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    power = runner.getDoubleArgumentValue('elevator_power_w', user_arguments)
    pattern = runner.getStringArgumentValue('definition_name_pattern', user_arguments).downcase

    if power <= 0
      runner.registerError('Elevator power must be greater than zero.')
      return false
    end

    matches = model.getElectricEquipmentDefinitions.select do |definition|
      definition.nameString.downcase.include?(pattern)
    end

    if matches.empty?
      available = model.getElectricEquipmentDefinitions.map(&:nameString).join(', ')
      runner.registerError(
        "No equipment definition matched '#{pattern}'. Available: #{available}"
      )
      return false
    end

    initial = matches.map do |definition|
      level = definition.designLevel
      "#{definition.nameString}=#{level.is_initialized ? level.get.round(1) : 'n/a'} W"
    end

    applied = 0
    instance_count = 0
    matches.each do |definition|
      # Tanim Watts/Area gibi baska bir yontem kullaniyorsa sessizce degistirmek
      # yerine atlanir; aksi halde toplam guc beklenmedik sekilde degisir.
      unless definition.designLevel.is_initialized
        runner.registerWarning(
          "#{definition.nameString} does not use an absolute design level; left unchanged."
        )
        next
      end
      definition.setDesignLevel(power)
      # instances() bir SWIG vektorudur; .length tanimli degil, .size kullanilir.
      instance_count += definition.instances.size
      applied += 1
    end

    if applied.zero?
      runner.registerError('Matched definitions do not use an absolute design level.')
      return false
    end

    runner.registerInitialCondition(initial.join('; '))
    runner.registerValue('elevator_power_w', power, 'W')
    runner.registerFinalCondition(
      "Set #{power} W on #{applied} definition(s) driving #{instance_count} instance(s)."
    )
    true
  rescue StandardError => e
    runner.registerError("Set Elevator Load failed: #{e.message}")
    false
  end
end

SetElevatorLoad.new.registerWithApplication
