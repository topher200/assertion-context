import { Component } from '@angular/core';
import { Traceback } from './traceback';
import { TracebackService } from './traceback.service';

@Component({
  selector: 'tracebacks',
  templateUrl: './tracebacks.component.html',
  styleUrls:['./tracebacks.component.css']
})
export class TracebacksComponent {
  heading = "Ultra Racing Schedule"
  cash = 10000;
  tracebacks: Traceback[];

  constructor(private tracebackService: TracebackService) { }

  ngOnInit() {
    this.tracebackService.getTracebacks()
        .subscribe(data => this.tracebacks = data);
  }

  totalCost() {
    let sum = 0;
    // if (this.races) {
    //   for (let race of this.races) {
    //     if (race.isRacing) sum += race.entryFee;
    //   }
    // }
    return sum;
  }

  castDate(date) {
    return new Date(date);
  }

  cashLeft() {
    return this.cash - this.totalCost();
  }

  enterRace(race) {
    if (this.cashLeft() > race.entryFee) {
      // race.isRacing = true;
    } else {
      alert("You don't have enough cash");
    }
  }

  cancelRace(race) {
    // race.isRacing = false;
  }
}
